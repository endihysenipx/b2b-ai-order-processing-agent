import base64
import hmac
import io
import logging

import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_auth_challenge_token,
    decode_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    hash_password,
    hash_recovery_code,
    new_totp_secret,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    TwoFactorChallengeRequest,
    TwoFactorLoginResponse,
    TwoFactorResetRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")
logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)) -> User:
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    password_matches = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not password_matches:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.must_change_password:
        return LoginResponse(
            challenge_token=create_auth_challenge_token(user.id, "password_change", user.auth_version),
            requires_password_change=True,
        )
    if not user.totp_enabled:
        return LoginResponse(
            challenge_token=create_auth_challenge_token(user.id, "2fa_setup", user.auth_version),
            requires_2fa_setup=True,
        )
    return LoginResponse(
        challenge_token=create_auth_challenge_token(user.id, "2fa_login", user.auth_version),
        requires_2fa=True,
    )


def _challenge_user(token: str, purpose: str, db: Session) -> User:
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication challenge") from exc
    if payload.get("token_type") != "auth_challenge" or payload.get("purpose") != purpose:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication challenge")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if payload.get("auth_version") != user.auth_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication challenge has been revoked")
    return user


def _login_response(user: User, recovery_codes: list[str] | None = None) -> TwoFactorLoginResponse:
    return TwoFactorLoginResponse(
        access_token=create_access_token(user.id, user.role, user.auth_version),
        user=user,
        recovery_codes=recovery_codes,
    )


@router.post("/password/change", response_model=LoginResponse)
def change_temporary_password(payload: PasswordChangeRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = _challenge_user(payload.challenge_token, "password_change", db)
    if not user.must_change_password:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Password change is not required")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.auth_version += 1
    db.commit()
    return LoginResponse(
        challenge_token=create_auth_challenge_token(user.id, "2fa_setup", user.auth_version),
        requires_2fa_setup=True,
    )


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_two_factor(payload: TwoFactorSetupRequest, db: Session = Depends(get_db)) -> TwoFactorSetupResponse:
    user = _challenge_user(payload.challenge_token, "2fa_setup", db)
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Two-factor authentication is already enabled")
    secret = new_totp_secret()
    user.totp_pending_secret_encrypted = encrypt_totp_secret(secret)
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="FlowForge Order Agent")
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    qr_data = base64.b64encode(output.getvalue()).decode()
    return TwoFactorSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_data_url=f"data:image/svg+xml;base64,{qr_data}",
    )


@router.post("/2fa/enable", response_model=TwoFactorLoginResponse)
def enable_two_factor(payload: TwoFactorChallengeRequest, db: Session = Depends(get_db)) -> TwoFactorLoginResponse:
    user = _challenge_user(payload.challenge_token, "2fa_setup", db)
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Two-factor authentication is already enabled")
    if not user.totp_pending_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start authenticator setup first")
    secret = decrypt_totp_secret(user.totp_pending_secret_encrypted)
    used_step = verify_totp(secret, payload.code, None)
    if used_step is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authenticator code")
    recovery_codes = generate_recovery_codes()
    user.totp_secret_encrypted = user.totp_pending_secret_encrypted
    user.totp_pending_secret_encrypted = None
    user.totp_enabled = True
    user.totp_last_used_step = used_step
    user.recovery_code_hashes = [hash_recovery_code(code) for code in recovery_codes]
    db.commit()
    return _login_response(user, recovery_codes)


@router.post("/2fa/verify", response_model=TwoFactorLoginResponse)
def verify_two_factor(payload: TwoFactorChallengeRequest, db: Session = Depends(get_db)) -> TwoFactorLoginResponse:
    user = _challenge_user(payload.challenge_token, "2fa_login", db)
    if not user.totp_enabled or not user.totp_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Authenticator setup is required")
    secret = decrypt_totp_secret(user.totp_secret_encrypted)
    used_step = verify_totp(secret, payload.code, user.totp_last_used_step)
    if used_step is not None:
        user.totp_last_used_step = used_step
        db.commit()
        return _login_response(user)
    candidate = hash_recovery_code(payload.code)
    recovery_hashes = list(user.recovery_code_hashes or [])
    matched = next((stored for stored in recovery_hashes if hmac.compare_digest(stored, candidate)), None)
    if matched is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authenticator or recovery code")
    recovery_hashes.remove(matched)
    user.recovery_code_hashes = recovery_hashes
    db.commit()
    return _login_response(user)


@router.post("/2fa/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_own_two_factor(
    payload: TwoFactorResetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove the current user's authenticator after re-authentication.

    Incrementing ``auth_version`` revokes existing REST and OAuth access. The
    next password login enters the normal authenticator enrollment flow.
    """
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid password or authenticator/recovery code",
    )
    if not verify_password(payload.password, current_user.password_hash):
        raise invalid_credentials
    if not current_user.totp_enabled or not current_user.totp_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Authenticator setup is not enabled")

    secret = decrypt_totp_secret(current_user.totp_secret_encrypted)
    used_step = verify_totp(secret, payload.code, current_user.totp_last_used_step)
    if used_step is None:
        candidate = hash_recovery_code(payload.code)
        recovery_hashes = list(current_user.recovery_code_hashes or [])
        if not any(hmac.compare_digest(stored, candidate) for stored in recovery_hashes):
            raise invalid_credentials

    current_user.totp_enabled = False
    current_user.totp_secret_encrypted = None
    current_user.totp_pending_secret_encrypted = None
    current_user.totp_last_used_step = None
    current_user.recovery_code_hashes = []
    current_user.auth_version += 1
    db.commit()
    logger.info("User reset own authenticator; user_id=%s", current_user.id)

import base64
import hashlib
import hmac
import secrets
import string
from datetime import UTC, datetime, timedelta

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _token(payload: dict, expires: datetime) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            **payload,
            "iss": settings.token_issuer,
            "aud": settings.token_audience,
            "iat": now,
            "nbf": now,
            "exp": expires,
            "jti": secrets.token_urlsafe(16),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_access_token(subject: str, role: str, auth_version: int) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return _token(
        {"sub": subject, "token_type": "access", "role": role, "auth_version": auth_version, "amr": ["pwd", "otp"]},
        expires,
    )


def create_auth_challenge_token(subject: str, purpose: str, auth_version: int) -> str:
    return _token(
        {
            "sub": subject,
            "token_type": "auth_challenge",
            "purpose": purpose,
            "auth_version": auth_version,
            "amr": ["pwd"],
        },
        datetime.now(UTC) + timedelta(minutes=5),
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience=settings.token_audience,
        issuer=settings.token_issuer,
        options={"require_sub": True, "require_exp": True, "require_iat": True},
    )


def _fernet() -> Fernet:
    material = (settings.totp_encryption_key or settings.secret_key).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(material).digest()))


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt authenticator secret") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32(length=32)


def verify_totp(secret: str, code: str, last_used_step: int | None) -> int | None:
    if not code.isdigit() or len(code) != 6:
        return None
    totp = pyotp.TOTP(secret, digits=6, interval=30)
    current_step = int(datetime.now(UTC).timestamp()) // 30
    for offset in (-1, 0, 1):
        step = current_step + offset
        if (last_used_step is None or step > last_used_step) and hmac.compare_digest(totp.at(step * 30), code):
            return step
    return None


def generate_recovery_codes(count: int = 10) -> list[str]:
    raw_codes = (secrets.token_hex(8).upper() for _ in range(count))
    return ["-".join(raw[index : index + 4] for index in range(0, 16, 4)) for raw in raw_codes]


def hash_recovery_code(code: str) -> str:
    normalized = code.replace("-", "").strip().upper().encode()
    return hmac.new(settings.secret_key.encode(), b"recovery-code:" + normalized, hashlib.sha256).hexdigest()


def generate_temporary_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
            and any(char in "!@#$%^&*" for char in password)
        ):
            return password


def validate_password_strength(password: str) -> None:
    if (
        len(password) < 12
        or not any(char.islower() for char in password)
        or not any(char.isupper() for char in password)
        or not any(char.isdigit() for char in password)
        or not any(not char.isalnum() for char in password)
    ):
        raise ValueError("Password must be at least 12 characters and include uppercase, lowercase, number, and symbol")

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_admin
from app.core.security import generate_temporary_password, hash_password
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.auth import UserAccessUpdate, UserAdminOut, UserCreate, UserCreatedResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserAdminOut])
def list_users(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> list[User]:
    return list(
        db.scalars(
            select(User).options(selectinload(User.clients)).where(User.is_deleted.is_(False)).order_by(User.email)
        )
    )


def _selected_clients(db: Session, client_ids: list[str]) -> list[Client]:
    unique_ids = set(client_ids)
    clients = list(db.scalars(select(Client).where(Client.id.in_(unique_ids)))) if unique_ids else []
    if len(clients) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="One or more clients do not exist")
    return clients


@router.post("", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> UserCreatedResponse:
    email = str(payload.email).strip().casefold()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    clients = _selected_clients(db, payload.client_ids)
    temporary_password = generate_temporary_password()
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(temporary_password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
    )
    user.clients = clients if payload.role == "operator" else []
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(user=user, temporary_password=temporary_password)


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user_access(
    user_id: str,
    payload: UserAccessUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> User:
    user = db.scalar(select(User).options(selectinload(User.clients)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and (not payload.is_active or payload.role != "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove your own administrator access")
    clients = _selected_clients(db, payload.client_ids)
    user.role = payload.role
    user.is_active = payload.is_active
    user.clients = clients if payload.role == "operator" else []
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = False
    user.is_deleted = True
    user.clients = []
    user.totp_enabled = False
    user.totp_secret_encrypted = None
    user.totp_pending_secret_encrypted = None
    user.totp_last_used_step = None
    user.recovery_code_hashes = []
    user.auth_version += 1
    db.commit()


@router.delete("/{user_id}/2fa", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_two_factor(
    user_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use a recovery code for your own account")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.totp_enabled = False
    user.totp_secret_encrypted = None
    user.totp_pending_secret_encrypted = None
    user.totp_last_used_step = None
    user.recovery_code_hashes = []
    user.auth_version += 1
    db.commit()

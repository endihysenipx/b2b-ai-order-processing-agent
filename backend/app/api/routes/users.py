from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.auth import UserAccessUpdate, UserAdminOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserAdminOut])
def list_users(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> list[User]:
    return list(db.scalars(select(User).options(selectinload(User.clients)).order_by(User.email)))


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
    clients = list(db.scalars(select(Client).where(Client.id.in_(set(payload.client_ids)))))
    if len(clients) != len(set(payload.client_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more clients do not exist")
    user.role = payload.role
    user.is_active = payload.is_active
    user.clients = clients if payload.role == "operator" else []
    db.commit()
    db.refresh(user)
    return user


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

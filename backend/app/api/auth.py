from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.db.models import User, utc_now
from app.security.auth import create_access_token, get_current_user, hash_password, verify_password
from app.security.tenant import ensure_tenant


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    tenant_id: str
    username: str
    password: str
    display_name: Optional[str] = None


class UserCreateRequest(BaseModel):
    tenant_id: str
    username: str
    password: str
    display_name: Optional[str] = None


class UserRead(BaseModel):
    id: str
    tenant_id: str
    username: str
    display_name: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserRead


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_session)) -> LoginResponse:
    ensure_tenant(db, request.tenant_id)
    username = request.username.strip()
    if not username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = db.exec(
        select(User).where(User.tenant_id == request.tenant_id, User.username == username)
    ).first()
    if user:
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        if request.display_name and request.display_name != user.display_name:
            user.display_name = request.display_name.strip()[:80]
            user.updated_at = utc_now()
            db.add(user)
            db.commit()
            db.refresh(user)
    else:
        user = User(
            tenant_id=request.tenant_id,
            username=username,
            display_name=(request.display_name or username).strip()[:80],
            password_hash=hash_password(request.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return LoginResponse(token=create_access_token(user), user=_user_read(user))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return _user_read(user)


@router.post("/users", response_model=UserRead)
def create_user(
    request: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> UserRead:
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Only administrator can create accounts")
    if request.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot create accounts for another tenant")
    username = request.username.strip()
    if not username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    existing = db.exec(
        select(User).where(User.tenant_id == request.tenant_id, User.username == username)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")
    user = User(
        tenant_id=request.tenant_id,
        username=username,
        display_name=(request.display_name or username).strip()[:80],
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_read(user)


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
    )


def _is_admin_user(user: User) -> bool:
    return user.username in {"admin", "admin_demo"}

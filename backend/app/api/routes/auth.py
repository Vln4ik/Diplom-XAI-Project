from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import decode_token
from app.models import User
from app.schemas import LoginRequest, LogoutRequest, MessageResponse, RefreshRequest, TokenResponse, UserSummary
from app.services.auth import authenticate_user, issue_tokens

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    tokens = issue_tokens(user)
    return TokenResponse(**tokens, user=UserSummary.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token type")
    user = db.scalar(select(User).where(User.id == decoded["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    tokens = issue_tokens(user)
    return TokenResponse(**tokens, user=UserSummary.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
def logout(_: LogoutRequest | None = None, user: User = Depends(get_current_user)) -> MessageResponse:
    return MessageResponse(message=f"Logged out: {user.email}")

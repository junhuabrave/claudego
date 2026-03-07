"""Google OAuth authentication endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import PriceAlert, User, UserWatchlist
from app.schemas.schemas import UserResponse, UserUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


class GoogleLoginRequest(BaseModel):
    credential: str    # Google ID token from the frontend
    session_id: str    # Current anonymous session ID (for watchlist migration)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/auth/google", response_model=LoginResponse)
async def google_login(
    payload: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a Google ID token, create/promote/merge the user, return a JWT.
    """
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    # 1. Verify Google token
    try:
        id_info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        logger.warning("Invalid Google token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_id = id_info["sub"]
    email = id_info.get("email", "")

    # 2. Find existing Google-authenticated user
    result = await db.execute(select(User).where(User.google_id == google_id))
    google_user = result.scalar_one_or_none()

    # 3. Find the anonymous user for the current session
    anon_result = await db.execute(
        select(User).where(User.session_id == payload.session_id)
    )
    anon_user = anon_result.scalar_one_or_none()

    if google_user is None:
        if anon_user is not None:
            # 3a. Promote the anonymous row to a Google-authenticated user
            anon_user.google_id = google_id
            anon_user.email = email
            anon_user.session_id = None
            await db.commit()
            await db.refresh(anon_user)
            user = anon_user
            logger.info("Promoted anon user id=%d to Google user %s", user.id, email)
        else:
            # 3b. No anon session found — create a fresh Google user
            user = User(google_id=google_id, email=email)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("Created new Google user id=%d email=%s", user.id, email)
    else:
        # 4. Google user already exists — merge anon data into it, then delete anon user
        if anon_user is not None and anon_user.id != google_user.id:
            await _merge_anon_into_user(db, anon_user_id=anon_user.id, target_user_id=google_user.id)
        user = google_user
        # Refresh email in case it changed
        if email and user.email != email:
            user.email = email
            await db.commit()
            await db.refresh(user)

    access_token = create_access_token(user.id)
    return LoginResponse(access_token=access_token, user=UserResponse.model_validate(user))


async def _merge_anon_into_user(
    db: AsyncSession, anon_user_id: int, target_user_id: int
) -> None:
    """Move watchlist + alerts from anon_user to target_user, then delete anon_user."""
    # Move watchlist rows (skip symbols already in target's watchlist)
    anon_wl = await db.execute(
        select(UserWatchlist).where(UserWatchlist.user_id == anon_user_id)
    )
    target_symbols_result = await db.execute(
        select(UserWatchlist.symbol).where(UserWatchlist.user_id == target_user_id)
    )
    target_symbols = {row[0] for row in target_symbols_result.fetchall()}

    for row in anon_wl.scalars().all():
        if row.symbol not in target_symbols:
            row.user_id = target_user_id

    # Move alerts
    await db.execute(
        update(PriceAlert)
        .where(PriceAlert.user_id == anon_user_id)
        .values(user_id=target_user_id)
    )

    # Delete anon user
    await db.execute(delete(User).where(User.id == anon_user_id))
    await db.commit()
    logger.info("Merged anon user id=%d into user id=%d", anon_user_id, target_user_id)


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user (anonymous or authenticated)."""
    return current_user


@router.patch("/auth/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display_name (and future profile fields)."""
    if payload.display_name is not None:
        current_user.display_name = payload.display_name.strip()
    await db.commit()
    await db.refresh(current_user)
    return current_user

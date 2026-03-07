"""JWT helpers and get_current_user FastAPI dependency."""

import datetime
import logging

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User

logger = logging.getLogger(__name__)


def create_access_token(user_id: int) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=settings.jwt_expire_days
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """Returns user_id or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolves the current user from:
    1. Authorization: Bearer <jwt>  — authenticated user
    2. X-Session-ID header          — anonymous user (find-or-create)
    """
    # --- Try JWT first ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        user_id = decode_access_token(token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    # --- Fallback: anonymous session ---
    session_id = request.headers.get("X-Session-ID", "").strip()
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: provide Authorization header or X-Session-ID",
        )

    result = await db.execute(select(User).where(User.session_id == session_id))
    user = result.scalar_one_or_none()
    if user is None:
        # Create anonymous user on first visit
        user = User(session_id=session_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created anonymous user session_id=%s id=%d", session_id, user.id)

    return user

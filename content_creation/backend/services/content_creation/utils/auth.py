"""JWT authentication dependency for FastAPI."""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.services.content_creation.config import settings

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer()


async def get_current_creator_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> UUID:
    """Extract and validate creator_id from JWT Bearer token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        creator_id_str: str | None = payload.get("sub")
        if creator_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
            )
        return UUID(creator_id_str)
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    except ValueError as exc:
        logger.warning("Invalid creator_id in token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid creator ID in token",
        ) from exc

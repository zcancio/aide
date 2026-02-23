"""API token management routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.db import user_conn
from backend.models.api_token import ApiTokenListItem, RevokeTokenRequest
from backend.models.user import User
from backend.repos import api_token_repo

router = APIRouter(prefix="/api/tokens", tags=["api_tokens"])


@router.get("")
async def list_tokens(
    user: User = Depends(get_current_user),
) -> list[ApiTokenListItem]:
    """List all API tokens for the current user."""
    async with user_conn(user.id) as conn:
        tokens = await api_token_repo.list_tokens(conn, user.id)
        return tokens


@router.post("/revoke")
async def revoke_token(
    request: RevokeTokenRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Revoke an API token."""
    async with user_conn(user.id) as conn:
        revoked = await api_token_repo.revoke_token(conn, request.token_id, user.id)

        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found.",
            )

        return {"status": "revoked"}

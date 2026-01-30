from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.models import Match, User


async def get_match_or_404(session: AsyncSession, match_id: int) -> Match:
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


def ensure_not_finalized(match: Match, message: str = "Cannot modify a finalized match") -> None:
    if match.is_finalized:
        raise HTTPException(status_code=400, detail=message)


def format_lock_detail(username: str | None) -> str:
    return f"Match is locked by {username or 'another user'}"


async def ensure_lock_owner(session: AsyncSession, match: Match, user: User) -> None:
    if match.locked_by_user_id and match.locked_by_user_id != user.id:
        locked_by = await session.get(User, match.locked_by_user_id)
        locked_name = locked_by.username if locked_by else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=format_lock_detail(locked_name),
        )


async def unlock_all_for_user(session: AsyncSession, user: User) -> None:
    await session.execute(
        update(Match)
        .where(Match.locked_by_user_id == user.id)
        .values(locked_by_user_id=None, locked_at=None)
    )

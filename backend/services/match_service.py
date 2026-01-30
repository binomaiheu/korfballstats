from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models import Match, User
from backend.services.collaboration import (
    is_collaborator,
    list_collaborators,
    remove_collaborator,
    add_collaborator,
)


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
        if is_collaborator(match.id, user.id):
            return
        locked_by = await session.get(User, match.locked_by_user_id)
        locked_name = locked_by.username if locked_by else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=format_lock_detail(locked_name),
        )


async def unlock_all_for_user(session: AsyncSession, user: User) -> list[tuple[int, int | None]]:
    result = await session.execute(
        select(Match).where(Match.locked_by_user_id == user.id)
    )
    matches = result.scalars().all()

    updates: list[tuple[int, int | None]] = []
    for match in matches:
        new_owner_id = await transfer_lock_on_owner_exit(session, match, user.id)
        updates.append((match.id, new_owner_id))
    return updates


async def transfer_lock_on_owner_exit(
    session: AsyncSession,
    match: Match,
    owner_user_id: int,
) -> int | None:
    collaborators = sorted(list_collaborators(match.id))
    remove_collaborator(match.id, owner_user_id)
    next_ids = [uid for uid in collaborators if uid != owner_user_id]

    if next_ids:
        new_owner_id = next_ids[0]
        match.locked_by_user_id = new_owner_id
        match.locked_at = datetime.now(timezone.utc)
        add_collaborator(match.id, new_owner_id)
        session.add(match)
        return new_owner_id

    match.locked_by_user_id = None
    match.locked_at = None
    session.add(match)
    return None

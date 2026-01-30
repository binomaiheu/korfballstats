from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.auth import get_current_user
from backend.db import get_session
from backend.schema import MatchCreate, MatchRead, TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead
from backend.schema import ActionRead
from backend.models import Match, Action, Team, User
from backend.services.match_service import (
    ensure_lock_owner,
    ensure_not_finalized,
    get_match_or_404,
    unlock_all_for_user,
    transfer_lock_on_owner_exit,
)
from backend.services.collaboration import add_collaborator, add_request, get_requests, pop_request, is_collaborator, list_collaborators
from backend.services.join_events import notify as notify_join
from backend.services.join_decision_events import notify as notify_join_decision
from backend.services.clock_events import notify as notify_clock
from backend.schema import UserRead

from logging import getLogger


logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/matches", tags=["Matches"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=List[MatchRead])
async def read_matches(with_team: bool = False, session: AsyncSession = Depends(get_session)):

    query = select(Match).options(selectinload(Match.team))

    result = await session.execute(query)
    matches = result.scalars().all()

    return [MatchRead.model_validate(match) for match in matches]


@router.get("/{match_id}", response_model=MatchRead)
async def get_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Match)
        .options(
            selectinload(Match.team)
        )
        .where(Match.id == match_id)
    )

    result = await session.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    return match


@router.post("", response_model=MatchRead)
async def create_match(data: MatchCreate, session: AsyncSession = Depends(get_session)):
    match = Match(**data.model_dump())

    try:
        session.add(match)

        await session.commit()
        await session.refresh(match, attribute_names=["team"])

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error creating new match in database"
        )

    return match


@router.put("/{match_id}", response_model=MatchRead)
async def update_match(match_id: int, data: MatchCreate, session: AsyncSession = Depends(get_session)):
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Cannot update a finalized match"
        )

    for key, value in data.model_dump().items():
        setattr(match, key, value)

    try:
        session.add(match)

        await session.commit()
        await session.refresh(match, attribute_names=["team"])

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error updating match in database"
        )

    return match


@router.delete("/{match_id}", status_code=204)
async def delete_match(match_id: int, session: AsyncSession = Depends(get_session)):
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        await session.delete(match)
        await session.commit()

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error deleting match from database"
        )


@router.get("/{match_id}/actions", response_model=list[ActionRead])
async def get_match_actions(
    match_id: int,
    session: AsyncSession = Depends(get_session),
):
    # Ensure match exists
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Fetch all actions for this match
    stmt = (
        select(Action, User.username)
        .join(User, User.id == Action.user_id, isouter=True)
        .where(Action.match_id == match_id)
    )

    result = await session.execute(stmt)
    rows = result.all()

    output = []
    for action, username in rows:
        data = ActionRead.model_validate(action).model_dump()
        data["username"] = username
        output.append(data)

    return output

@router.post("/{match_id}/finalize", response_model=MatchRead)
async def finalize_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)

    await ensure_lock_owner(session, match, user)

    match.is_finalized = True

    try:
        session.add(match)

        await session.commit()
        await session.refresh(match, attribute_names=["team"])

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error finalizing match in database"
        )

    return match

@router.post("/{match_id}/time_registered", response_model=MatchRead)
async def register_time(match_id: int, t_reg: int, session: AsyncSession = Depends(get_session)):
    match = await get_match_or_404(session, match_id)
    
    ensure_not_finalized(match, "Cannot update time for a finalized match")

    match.time_registered_s = t_reg

    try:
        session.add(match)

        await session.commit()
        await session.refresh(match, attribute_names=["team"])

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error registering time in database"
        )

    return match


@router.post("/{match_id}/lock", status_code=200)
async def lock_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)

    ensure_not_finalized(match, "Cannot lock a finalized match")

    if match.locked_by_user_id and match.locked_by_user_id != user.id:
        if is_collaborator(match_id, user.id):
            return {"detail": "collaborator"}
        return {"detail": "locked"}

    match.locked_by_user_id = user.id
    match.locked_at = datetime.now(timezone.utc)
    add_collaborator(match_id, user.id)

    try:
        session.add(match)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Error locking match")

    return {"detail": "ok"}


@router.post("/{match_id}/unlock", status_code=200)
async def unlock_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)

    await ensure_lock_owner(session, match, user)

    try:
        new_owner_id = await transfer_lock_on_owner_exit(session, match, user.id)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Error unlocking match")

    notify_clock(match_id, {"locked_by_user_id": new_owner_id})
    return {"detail": "ok"}


@router.post("/unlock_all", status_code=200)
async def unlock_all_matches(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    updates = await unlock_all_for_user(session, user)
    await session.commit()
    for match_id, new_owner_id in updates:
        notify_clock(match_id, {"locked_by_user_id": new_owner_id})
    return {"detail": "ok"}


@router.get("/{match_id}/join_requests")
async def list_join_requests(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)
    await ensure_lock_owner(session, match, user)
    return [
        {
            "match_id": req.match_id,
            "requester": UserRead(id=req.requester_user_id, username=req.requester_username, is_active=True).model_dump(),
            "created_at": req.created_at,
        }
        for req in get_requests(match_id)
    ]


@router.get("/{match_id}/collaborators")
async def list_collaborators_for_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
):
    match = await get_match_or_404(session, match_id)
    owner_id = match.locked_by_user_id
    collaborator_ids = list_collaborators(match_id)

    user_ids = set(collaborator_ids)
    if owner_id:
        user_ids.add(owner_id)

    usernames: dict[int, str] = {}
    if user_ids:
        stmt = select(User).where(User.id.in_(user_ids))
        result = await session.execute(stmt)
        for user in result.scalars().all():
            usernames[user.id] = user.username

    owner = None
    if owner_id:
        owner = {"id": owner_id, "username": usernames.get(owner_id)}

    collaborators = [
        {"id": uid, "username": usernames.get(uid)}
        for uid in collaborator_ids
        if uid != owner_id
    ]

    return {"owner": owner, "collaborators": collaborators}


@router.post("/{match_id}/join_request")
async def request_join(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)
    if match.locked_by_user_id == user.id:
        return {"detail": "already owner"}
    add_request(match_id, user.id, user.username)
    notify_join(match_id, user.username)
    return {"detail": "requested"}


@router.post("/{match_id}/join_decision")
async def decide_join(
    match_id: int,
    requester_user_id: int,
    accept: bool,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    match = await get_match_or_404(session, match_id)
    await ensure_lock_owner(session, match, user)
    req = pop_request(match_id, requester_user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if accept:
        add_collaborator(match_id, requester_user_id)
        notify_join_decision(
            requester_user_id,
            {"match_id": match_id, "approved": True, "owner_username": user.username},
        )
        return {"detail": "accepted"}
    notify_join_decision(
        requester_user_id,
        {"match_id": match_id, "approved": False, "owner_username": user.username},
    )
    return {"detail": "denied"}

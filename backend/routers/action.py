from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.auth import get_current_user
from backend.db import get_session
from backend.schema import ActionRead, ActionCreate
from backend.models import Action, Match, User
from backend.services.match_service import ensure_lock_owner, ensure_not_finalized


router = APIRouter(prefix="/actions", tags=["Actions"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ActionRead)
async def add_action(
    action: ActionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Check if match exists and is not finalized
    match = await session.get(Match, action.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    ensure_not_finalized(match, "Cannot add actions to a finalized match")
    await ensure_lock_owner(session, match, user)

    action_payload = action.model_dump()
    if action_payload.get("is_opponent"):
        action_payload["player_id"] = None
    action_payload["user_id"] = user.id
    action = Action(**action_payload)

    try:
        session.add(action)

        await session.commit()
        await session.refresh(action)

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error creating new action in database"
        )
    
    return action


@router.get("/{action_id}", response_model=ActionRead)
async def read_action(action_id: int, session: AsyncSession = Depends(get_session)):
    statement = select(Action).where(Action.id == action_id)
    result = await session.execute(statement)
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return result.scalar_one_or_none()


@router.put("/{action_id}", response_model=ActionRead)
async def edit_action(
    action_id: int,
    action_update: ActionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    action = await session.get(Action, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Check if match is finalized
    match = await session.get(Match, action.match_id)
    if match:
        ensure_not_finalized(match, "Cannot edit actions in a finalized match")
        await ensure_lock_owner(session, match, user)
    
    if match.locked_by_user_id and match.locked_by_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is locked by another user")

    for key, value in action_update.model_dump().items():
        if key == "user_id":
            continue
        if hasattr(action, key):
            setattr(action, key, value)

    try:
        session.add(action)
        await session.commit()
        await session.refresh(action)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error updating action"
        )

    return action


@router.delete("/{action_id}", status_code=204)
async def remove_action(
    action_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    action = await session.get(Action, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Check if match is finalized
    match = await session.get(Match, action.match_id)
    if match:
        ensure_not_finalized(match, "Cannot delete actions from a finalized match")
        await ensure_lock_owner(session, match, user)

    try:
        await session.delete(action)
        await session.commit()

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error deleting action from database"
        )

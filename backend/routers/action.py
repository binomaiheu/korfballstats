from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.db import get_session
from backend.schema import ActionRead, ActionCreate
from backend.models import Action, Match


router = APIRouter(prefix="/actions", tags=["Actions"])


@router.post("", response_model=ActionRead)
async def add_action(action: ActionCreate, session: AsyncSession = Depends(get_session)):
    # Check if match exists and is not finalized
    match = await session.get(Match, action.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Cannot add actions to a finalized match"
        )

    action = Action(**action.model_dump())

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
async def edit_action(action_id: int, action_update: ActionCreate, session: AsyncSession = Depends(get_session)):
    action = await session.get(Action, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Check if match is finalized
    match = await session.get(Match, action.match_id)
    if match and match.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit actions in a finalized match"
        )
    
    for key, value in action_update.model_dump().items():
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
async def remove_action(action_id: int, session: AsyncSession = Depends(get_session)):
    action = await session.get(Action, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Check if match is finalized
    match = await session.get(Match, action.match_id)
    if match and match.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete actions from a finalized match"
        )

    try:
        await session.delete(action)
        await session.commit()

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error deleting action from database"
        )

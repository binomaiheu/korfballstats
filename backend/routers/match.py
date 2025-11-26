from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.db import get_session
from backend.schema import MatchReadWithTeam, TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead

from backend.models import Match
from backend.schema import MatchCreate, MatchRead

from logging import getLogger


logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=Union[List[MatchRead], List[MatchReadWithTeam]])
async def read_matches(with_team: bool = False, session: AsyncSession = Depends(get_session)):

    query = select(Match)
    if with_team:
        query = query.options(selectinload(Match.team))

    result = await session.execute(query)
    matches = result.scalars().all()

    if with_team:
        return [MatchReadWithTeam.model_validate(match) for match in matches]
    else:   
        return [MatchRead.model_validate(match) for match in matches]


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

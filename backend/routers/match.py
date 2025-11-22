from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.db import get_session
from backend.schema import TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead

from backend.models import Match
from backend.schema import MatchCreate, MatchRead

from logging import getLogger


logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=list[MatchRead])
async def read_matches(session: AsyncSession = Depends(get_session)):

    query = select(Match).options(selectinload(Match.team))

    result = await session.execute(query)
    matches = result.scalars().all()

    return [MatchRead.model_validate(match) for match in matches]


@router.post("", response_model=MatchRead)
async def create_match(data: MatchCreate, session: AsyncSession = Depends(get_session)):
    match = Match(**data.model_dump())

    try:
        session.add(match)

        await session.commit()
        await session.refresh(match)

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error creating new match in database"
        )

    return match
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.db import get_session
from backend.schema import TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead

from backend.models import Team, Player, team_player_link
from backend.schema import PlayerCreate, PlayerRead, PlayerReadWithTeams

from logging import getLogger


logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("", response_model=Union[List[PlayerRead], List[PlayerReadWithTeams]])
async def read_players(with_teams: bool = False, session: AsyncSession = Depends(get_session)):
    query = select(Player)

    if with_teams:
        query = query.options(selectinload(Player.teams))

    result = await session.execute(query)
    players = result.scalars().all()

    # FastAPI + Pydantic will detect whether each item has a `teams` field
    if with_teams:
        return [PlayerReadWithTeams.model_validate(player) for player in players]
    else:
        return [PlayerRead.model_validate(player) for player in players]


@router.post("", response_model=PlayerRead)
async def create_player(data: PlayerCreate, session: AsyncSession = Depends(get_session)):

    player = Player(**data.model_dump())

    try:
        session.add(player)

        await session.commit()
        await session.refresh(player)
    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error creating new player in database"
        )

    return player

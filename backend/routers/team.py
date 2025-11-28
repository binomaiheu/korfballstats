from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.db import get_session
from backend.schema import TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead, MatchRead

from backend.models import Team, Player, team_player_link, Match
from backend.schema import TeamRead, TeamReadWithPlayers

from logging import getLogger


logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=Union[List[TeamRead], List[TeamReadWithPlayers]])
async def read_teams(with_players: bool = False, session: AsyncSession = Depends(get_session)):
    query = select(Team)

    if with_players:
        query = query.options(selectinload(Team.players))

    result = await session.execute(query)
    teams = result.scalars().all()

    # FastAPI + Pydantic will detect whether each item has a `players` field
    if with_players:
        return [TeamReadWithPlayers.model_validate(team) for team in teams]
    else:
        return [TeamRead.model_validate(team) for team in teams]


@router.get("/{team_id}", response_model=Union[TeamRead, TeamReadWithPlayers])
async def read_team(team_id: int, with_players: bool = False, session: AsyncSession = Depends(get_session)):
    
    query = select(Team).where(Team.id == team_id)
    if with_players:
        query = query.options(selectinload(Team.players))

    team = await session.scalar(query)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    if with_players:
        return TeamReadWithPlayers.model_validate(team)
    else:
        return TeamRead.model_validate(team)
    

@router.get("/{team_id}/matches", response_model=List[MatchRead])
async def read_team_matches(team_id: int, session: AsyncSession = Depends(get_session)):

    query = select(Match)\
        .options(selectinload(Match.team))\
        .where(Match.team_id == team_id)

    matches = await session.execute(query)
    matches = matches.scalars().all()

    return [MatchRead.model_validate(match) for match in matches]


@router.post("", response_model=TeamRead)
async def create_team(data: TeamCreate, session: AsyncSession = Depends(get_session)):

    team = Team(**data.model_dump())

    try:
        session.add(team)

        await session.commit()
        await session.refresh(team)

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Error creating new team in database"
        )

    return team


@router.put("/{team_id}", response_model=TeamRead)
async def update_team(team_id: int, data: TeamCreate, session: AsyncSession = Depends(get_session)):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    for key, value in data.model_dump().items():
        setattr(team, key, value)

    try:
        await session.commit()
        await session.refresh(team)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error updating team in database"
        )

    return team

@router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: int, session: AsyncSession = Depends(get_session)):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    try:
        await session.delete(team)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error deleting team from database"
        )


@router.post("/assign", status_code=200)
async def assign_player(data: TeamAssignPlayer, session: AsyncSession = Depends(get_session)):
    
    logger.info(f"Assigning {data.team_id}, {data.player_id}")

    try:
        team = await session.get(Team, data.team_id, options=[selectinload(Team.players)])
        player = await session.get(Player, data.player_id)

        if not team or not player:
            raise HTTPException(
                status_code=404,
                detail="Team or Player not found"
            )

        if player in team.players:
            logger.warning(f"Player {data.player_id} is already assigned to team {data.team_id}")
            raise HTTPException(
                status_code=400,
                detail="Player already assigned to team"
            )

        team.players.append(player)

        await session.commit()    

        return {"detail": "ok"}

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error assigning player to team in database"
        )


@router.post("/unassign", status_code=200)
async def unassign_player(data: TeamAssignPlayer, session: AsyncSession = Depends(get_session)):

    logger.info(f"Unassigning {data.team_id}, {data.player_id}")

    try:
        team = await session.get(Team, data.team_id, options=[selectinload(Team.players)])
        player = await session.get(Player, data.player_id)

        if not team or not player:
            raise HTTPException(
                status_code=404,
                detail="Team or Player not found"
            )

        if player not in team.players:
            logger.warning(f"Player {data.player_id} is not assigned to team {data.team_id}")
            raise HTTPException(
                status_code=400,
                detail="Player not assigned to team"
            )

        team.players.remove(player)

        await session.commit()

        return {"detail": "ok"}

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error unassigning player from team in database"
        )


@router.get("/{team_id}/players", response_model=List[PlayerRead])
async def list_team_players(team_id: int, session: AsyncSession = Depends(get_session)):
    
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    stmt = (
        select(Player)
        .join(team_player_link, Player.id == team_player_link.c.player_id)
        .where(team_player_link.c.team_id == team_id)
        .order_by(Player.name)
    )

    result = await session.execute(stmt)
    return result.scalars().all()
    
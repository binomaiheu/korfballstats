from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.schema import TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead
from backend.crud.team import get_teams, create_team, add_player_to_team, get_players_for_team

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamRead])
async def read_teams(session: AsyncSession = Depends(get_session)):
    return await get_teams(session)


@router.post("", response_model=TeamRead)
async def create_team_ep(data: TeamCreate, session: AsyncSession = Depends(get_session)):
    return await create_team(session, data.name)


@router.post("/assign", status_code=200)
async def assign_player_ep(data: TeamAssignPlayer, session: AsyncSession = Depends(get_session)):
    await add_player_to_team(session, data.team_id, data.player_id)
    return {"status": "ok"}

@router.get("/{team_id}/players", response_model=list[PlayerRead])
async def list_players_for_team(team_id: int, db: AsyncSession = Depends(get_session)):
    return await get_players_for_team(db, team_id)
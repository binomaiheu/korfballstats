from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.schema import PlayerCreate, PlayerRead
from backend.crud.player import create_player, get_players

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("", response_model=list[PlayerRead])
async def read_players(session: AsyncSession = Depends(get_session)):
    return await get_players(session)


@router.post("", response_model=PlayerRead)
async def create_player_ep(data: PlayerCreate, session: AsyncSession = Depends(get_session)):
    return await create_player(session, data.name)

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.schema import MatchCreate, MatchRead
from backend.crud.match import get_matches, create_match

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=list[MatchRead])
async def read_matches(session: AsyncSession = Depends(get_session)):
    return await get_matches(session)


@router.post("", response_model=MatchRead)
async def create_match_ep(data: MatchCreate, session: AsyncSession = Depends(get_session)):
    return await create_match(session, team_id=data.team_id, opponent_name=data.opponent_name)

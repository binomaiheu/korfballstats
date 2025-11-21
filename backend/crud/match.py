from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from backend.models import Match


async def get_matches(session: AsyncSession):
    matches = await session.exec(select(Match))
    return matches.scalars().all()


async def create_match(session: AsyncSession, team_id: int, opponent_name: str):
    match = Match(team_id=team_id, opponent_name=opponent_name)
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return match


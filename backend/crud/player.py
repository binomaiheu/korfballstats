from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from backend.models import Player


async def get_players(session: AsyncSession):
    players = await session.execute(select(Player))
    return players.scalars().all()


async def create_player(session: AsyncSession, name: str):
    player = Player(name=name)
    session.add(player)
    await session.commit()
    await session.refresh(player)
    return player

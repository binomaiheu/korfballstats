from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from backend.models import Team, Player, team_player_link


async def get_teams(session: AsyncSession):
    teams = await session.execute(
        select(Team).options(selectinload(Team.players))
    )

    return teams.scalars().all()

async def create_team(session: AsyncSession, name: str):
    team = Team(name=name)
    session.add(team)
    await session.commit()
    await session.refresh(team)
    return team


async def add_player_to_team(session: AsyncSession, team_id: int, player_id: int):
    team = await session.get(Team, team_id)
    player = await session.get(Player, player_id)

    team.players.append(player)
    await session.commit()

    return player


async def get_players_for_team(session: AsyncSession, team_id: int):
    stmt = (
        select(Player)
        .join(team_player_link, Player.id == team_player_link.c.player_id)
        .where(team_player_link.c.team_id == team_id)
    )

    result = await session.execute(stmt)
    return result.scalars().all()


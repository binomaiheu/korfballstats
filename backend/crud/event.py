

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.models import Event, EventType


async def create_event(session: AsyncSession, match_id: int, player_id: int, team_id: int, type: EventType, value: int) -> Event:
    event = Event(
        match_id=match_id,
        player_id=player_id,
        team_id=team_id,
        type=type,
        value=value,
    )
    session.add(event)
    
    await session.commit()
    await session.refresh(event)
    return event

async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    statement = select(Event).where(Event.id == event_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def get_events(session: AsyncSession) -> list[Event]:
    statement = select(Event)
    results = await session.execute(statement)
    return results.scalars().all()

async def update_event(session: AsyncSession, event_id: int, **kwargs) -> Event | None:
    event = await get_event(session, event_id)
    if not event:
        return None
    for key, value in kwargs.items():
        if hasattr(event, key):
            setattr(event, key, value)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

async def delete_event(session: AsyncSession, event_id: int) -> bool:
    event = await get_event(session, event_id)
    if not event:
        return False
    await session.delete(event)
    await session.commit()
    return True
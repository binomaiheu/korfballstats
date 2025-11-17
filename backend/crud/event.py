
from sqlmodel import Session, select
from backend.models import Event, EventType


def create_event(session: Session, match_id: int, player_id: int, team_id: int, type: EventType, value: int) -> Event:
    event = Event(
        match_id=match_id,
        player_id=player_id,
        team_id=team_id,
        type=type,
        value=value,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

def get_event(session: Session, event_id: int) -> Event | None:
    statement = select(Event).where(Event.id == event_id)
    result = session.exec(statement).first()
    return result

def get_events(session: Session) -> list[Event]:
    statement = select(Event)
    results = session.exec(statement).all()
    return results

def update_event(session: Session, event_id: int, **kwargs) -> Event | None:
    event = get_event(session, event_id)
    if not event:
        return None
    for key, value in kwargs.items():
        if hasattr(event, key):
            setattr(event, key, value)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

def delete_event(session: Session, event_id: int) -> bool:
    event = get_event(session, event_id)
    if not event:
        return False
    session.delete(event)
    session.commit()
    return True
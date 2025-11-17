from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from backend.db import get_session
from backend.crud.event import create_event, get_event, get_events, update_event, delete_event
from backend.schema import Event, EventCreate

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("", response_model=EventCreate)
def add_event(event: EventCreate, session: Session = Depends(get_session)):
    return create_event(session, **event.model_dump())

@router.get("/{event_id}", response_model=Event)
def read_event(event_id: int, session: Session = Depends(get_session)):
    event = get_event(session, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.get("", response_model=list[Event])
def read_events(session: Session = Depends(get_session)):
    return get_events(session)

@router.put("/{event_id}", response_model=EventCreate)
def edit_event(event_id: int, event_update: EventCreate, session: Session = Depends(get_session)):
    event = update_event(session, event_id, **event_update.model_dump())
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.delete("/{event_id}", response_model=bool)
def remove_event(event_id: int, session: Session = Depends(get_session)):
    success = delete_event(session, event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return success
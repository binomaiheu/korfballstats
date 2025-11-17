from fastapi import APIRouter, Depends
from sqlmodel import Session
from backend.db import get_session
from backend.schema import PlayerCreate, PlayerRead
from backend.crud.player import create_player, get_players

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("", response_model=list[PlayerRead])
def read_players(session: Session = Depends(get_session)):
    return get_players(session)


@router.post("", response_model=PlayerRead)
def create_player_ep(data: PlayerCreate, session: Session = Depends(get_session)):
    return create_player(session, data.name)

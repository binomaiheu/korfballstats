from fastapi import APIRouter, Depends
from sqlmodel import Session
from backend.db import get_session
from backend.schema import MatchCreate, MatchRead
from backend.crud.match import get_matches, create_match

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=list[MatchRead])
def read_matches(session: Session = Depends(get_session)):
    return get_matches(session)


@router.post("", response_model=MatchRead)
def create_match_ep(data: MatchCreate, session: Session = Depends(get_session)):
    return create_match(session, team_id=data.team_id, opponent_name=data.opponent_name)

from fastapi import APIRouter, Depends
from sqlmodel import Session
from backend.db import get_session
from backend.schema import TeamCreate, TeamRead, TeamAssignPlayer, PlayerRead
from backend.crud.team import get_teams, create_team, add_player_to_team, get_players_for_team

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamRead])
def read_teams(session: Session = Depends(get_session)):
    return get_teams(session)


@router.post("", response_model=TeamRead)
def create_team_ep(data: TeamCreate, session: Session = Depends(get_session)):
    return create_team(session, data.name)


@router.post("/assign", status_code=200)
def assign_player_ep(data: TeamAssignPlayer, session: Session = Depends(get_session)):
    add_player_to_team(session, data.team_id, data.player_id)
    return {"status": "ok"}

@router.get("/{team_id}/players", response_model=list[PlayerRead])
def list_players_for_team(team_id: int, db: Session = Depends(get_session)):
    return get_players_for_team(db, team_id)
from sqlmodel import Session, select
from backend.models import Match


def get_matches(session: Session):
    return session.exec(select(Match)).all()


def create_match(session: Session, team_id: int, opponent_name: str):
    match = Match(team_id=team_id, opponent_name=opponent_name)
    session.add(match)
    session.commit()
    session.refresh(match)
    return match
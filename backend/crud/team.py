from sqlmodel import Session, select
from backend.models import Team, TeamPlayerLink, Player


def get_teams(session: Session):
    return session.exec(select(Team)).all()


def create_team(session: Session, name: str):
    team = Team(name=name)
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def add_player_to_team(session: Session, team_id: int, player_id: int):
    link = TeamPlayerLink(team_id=team_id, player_id=player_id)
    session.add(link)
    session.commit()
    return link

def get_players_for_team(session: Session, team_id: int):
    statement = (
        select(Player)
        .join(TeamPlayerLink, Player.id == TeamPlayerLink.player_id)
        .where(TeamPlayerLink.team_id == team_id)
    )
    return session.exec(statement).all()
from sqlmodel import Session, select
from backend.models import Player


def get_players(session: Session):
    return session.exec(select(Player)).all()


def create_player(session: Session, name: str):
    player = Player(name=name)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player

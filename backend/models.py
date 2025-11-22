from sqlalchemy import Boolean, Integer, String, UniqueConstraint, ForeignKey, Enum, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import Optional, List
from enum import Enum as PyEnum
from datetime import datetime

from .db import engine


class EventType(str, PyEnum):
    GOAL = "goal"
    GOAL_FREE_THROW = "goal_free_throw"
    GOAL_INSIDE = "goal_inside"
    SHOT = "shot"
    FOUL = "foul"
    PENALTY = "penalty"


class Base(DeclarativeBase):
    pass

team_player_link = Table(
    "team_player_link",
    Base.metadata,
    Column("team_id", ForeignKey("team.id"), primary_key=True),
    Column("player_id", ForeignKey("player.id"), primary_key=True),
)


class Team(Base):
    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    players: Mapped[List["Player"]] = relationship("Player", secondary=team_player_link, back_populates="teams")
    matches: Mapped[List["Match"]] = relationship("Match", back_populates="team")


class Player(Base):
    __tablename__ = "player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    last_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    teams: Mapped[List[Team]] = relationship("Team", secondary=team_player_link, back_populates="players")

    __table_args__ = (
        UniqueConstraint("first_name", "last_name"),
    )


class Match(Base):
    __tablename__ = "match"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(default=datetime.now)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    opponent_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="matches")

class MatchLineup(Base):
    __tablename__ = "match_lineup"

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))

    type: Mapped[EventType] = mapped_column(Enum(EventType))
    value: Mapped[int] = mapped_column(Integer)

    timestamp: Mapped[datetime] = mapped_column(default=datetime.now)

    match: Mapped["Match"] = relationship("Match")
    player: Mapped["Player"] = relationship("Player")
    team: Mapped["Team"] = relationship("Team")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
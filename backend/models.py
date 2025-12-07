from sqlalchemy import Boolean, Integer, String, UniqueConstraint, ForeignKey, Enum, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import Optional, List
from datetime import datetime


from .schema import ActionType, MatchType, SexType
from .db import engine



class Base(DeclarativeBase):
    pass

team_player_link = Table(
    "team_player_link",
    Base.metadata,
    Column("team_id", ForeignKey("team.id"), primary_key=True),
    Column("player_id", ForeignKey("player.id"), primary_key=True),
)



class MatchPlayerLink(Base):
    __tablename__ = "match_player_link"

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), primary_key=True)

    time_played: Mapped[int] = mapped_column(Integer, default=0)  # time played in this match in seconds



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
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    sex: Mapped[Optional[SexType]] = mapped_column(Enum(SexType), nullable=False)

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
    match_type: Mapped[Optional[MatchType]] = mapped_column(Enum(MatchType), default=MatchType.NORMAL)
    time_registered_s: Mapped[int] = mapped_column(Integer, default=0)  # in seconds
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False)


    team: Mapped["Team"] = relationship("Team", back_populates="matches")


class Action(Base):
    __tablename__ = "action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))

    timestamp: Mapped[int] = mapped_column()
    x: Mapped[float] = mapped_column()
    y: Mapped[float] = mapped_column()
    period: Mapped[int] = mapped_column()
    action: Mapped[ActionType] = mapped_column(Enum(ActionType))
    result: Mapped[bool] = mapped_column(Boolean, default=False)
 
    match: Mapped["Match"] = relationship("Match")
    player: Mapped["Player"] = relationship("Player")


class Playtime(Base):
    __tablename__ = "playtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))

    time_played: Mapped[int] = mapped_column(default=0)  # in seconds
 
    match: Mapped["Match"] = relationship("Match")
    player: Mapped["Player"] = relationship("Player")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
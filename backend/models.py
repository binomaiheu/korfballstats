from sqlalchemy import Boolean, Integer, String, UniqueConstraint, ForeignKey, Enum, Table, Column, text
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
    x: Mapped[Optional[float]] = mapped_column(nullable=True)
    y: Mapped[Optional[float]] = mapped_column(nullable=True)
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
        await _migrate_action_coordinates_nullable(conn)


async def _migrate_action_coordinates_nullable(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(action)"))
    columns = {row[1]: row for row in result.fetchall()}  # name -> row tuple
    if not columns:
        return
    x_info = columns.get("x")
    y_info = columns.get("y")
    if not x_info or not y_info:
        return
    x_notnull = bool(x_info[3])
    y_notnull = bool(y_info[3])
    if not (x_notnull or y_notnull):
        return

    await conn.execute(text("PRAGMA foreign_keys=off"))
    await conn.execute(text("BEGIN"))
    try:
        await conn.execute(text("ALTER TABLE action RENAME TO action_old"))
        await conn.execute(text("""
            CREATE TABLE action (
                id INTEGER PRIMARY KEY,
                match_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                x FLOAT,
                y FLOAT,
                period INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                result BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY(match_id) REFERENCES match(id),
                FOREIGN KEY(player_id) REFERENCES player(id)
            )
        """))
        await conn.execute(text("""
            INSERT INTO action (id, match_id, player_id, timestamp, x, y, period, action, result)
            SELECT id, match_id, player_id, timestamp, x, y, period, action, result
            FROM action_old
        """))
        await conn.execute(text("DROP TABLE action_old"))
        await conn.execute(text("COMMIT"))
    except Exception:
        await conn.execute(text("ROLLBACK"))
        raise
    finally:
        await conn.execute(text("PRAGMA foreign_keys=on"))
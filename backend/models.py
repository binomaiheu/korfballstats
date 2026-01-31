from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, ForeignKey, Enum, Table, Column, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import Optional, List
from datetime import datetime, timezone
import sqlite3


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
    current_period: Mapped[int] = mapped_column(Integer, default=1)
    period_minutes: Mapped[int] = mapped_column(Integer, default=25)
    total_periods: Mapped[int] = mapped_column(Integer, default=2)
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


    team: Mapped["Team"] = relationship("Team", back_populates="matches")
    locked_by: Mapped[Optional["User"]] = relationship("User")


class Action(Base):
    __tablename__ = "action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("player.id"), nullable=True)
    is_opponent: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    timestamp: Mapped[int] = mapped_column()
    x: Mapped[Optional[float]] = mapped_column(nullable=True)
    y: Mapped[Optional[float]] = mapped_column(nullable=True)
    period: Mapped[int] = mapped_column()
    action: Mapped[ActionType] = mapped_column(Enum(ActionType))
    result: Mapped[bool] = mapped_column(Boolean, default=False)
 
    match: Mapped["Match"] = relationship("Match")
    player: Mapped["Player"] = relationship("Player")
    user: Mapped[Optional["User"]] = relationship("User")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Playtime(Base):
    __tablename__ = "playtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))

    time_played: Mapped[int] = mapped_column(default=0)  # in seconds
 
    match: Mapped["Match"] = relationship("Match")
    player: Mapped["Player"] = relationship("Player")


async def init_db():
    try:
        with sqlite3.connect("korfball.db") as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
    except sqlite3.Error:
        pass
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_action_coordinates_nullable(conn)
        await _migrate_action_user_id_nullable(conn)
        await _migrate_action_opponent_fields(conn)
        await _migrate_match_lock_columns(conn)
        await _migrate_match_current_period(conn)
        await _migrate_match_time_settings(conn)


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


async def _migrate_action_user_id_nullable(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(action)"))
    columns = {row[1]: row for row in result.fetchall()}
    if not columns or "user_id" in columns:
        return
    await conn.execute(text("ALTER TABLE action ADD COLUMN user_id INTEGER"))


async def _migrate_action_opponent_fields(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(action)"))
    columns = {row[1]: row for row in result.fetchall()}
    if not columns:
        return
    if "is_opponent" not in columns:
        await conn.execute(text("ALTER TABLE action ADD COLUMN is_opponent BOOLEAN DEFAULT 0"))
    player_info = columns.get("player_id")
    if player_info and player_info[3]:
        await conn.execute(text("PRAGMA foreign_keys=off"))
        await conn.execute(text("BEGIN"))
        try:
            await conn.execute(text("ALTER TABLE action RENAME TO action_old"))
            await conn.execute(text("""
                CREATE TABLE action (
                    id INTEGER PRIMARY KEY,
                    match_id INTEGER NOT NULL,
                    player_id INTEGER,
                    is_opponent BOOLEAN DEFAULT 0,
                    timestamp INTEGER NOT NULL,
                    x FLOAT,
                    y FLOAT,
                    period INTEGER NOT NULL,
                    action VARCHAR NOT NULL,
                    result BOOLEAN NOT NULL DEFAULT 0,
                    user_id INTEGER,
                    FOREIGN KEY(match_id) REFERENCES match(id),
                    FOREIGN KEY(player_id) REFERENCES player(id)
                )
            """))
            await conn.execute(text("""
                INSERT INTO action (id, match_id, player_id, is_opponent, timestamp, x, y, period, action, result, user_id)
                SELECT id, match_id, player_id, COALESCE(is_opponent, 0), timestamp, x, y, period, action, result, user_id
                FROM action_old
            """))
            await conn.execute(text("DROP TABLE action_old"))
            await conn.execute(text("COMMIT"))
        except Exception:
            await conn.execute(text("ROLLBACK"))
            raise
        finally:
            await conn.execute(text("PRAGMA foreign_keys=on"))


async def _migrate_match_lock_columns(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(match)"))
    columns = {row[1]: row for row in result.fetchall()}
    if not columns:
        return
    if "locked_by_user_id" not in columns:
        await conn.execute(text("ALTER TABLE match ADD COLUMN locked_by_user_id INTEGER"))
    if "locked_at" not in columns:
        await conn.execute(text("ALTER TABLE match ADD COLUMN locked_at DATETIME"))


async def _migrate_match_current_period(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(match)"))
    columns = {row[1]: row for row in result.fetchall()}
    if not columns:
        return
    if "current_period" not in columns:
        await conn.execute(text("ALTER TABLE match ADD COLUMN current_period INTEGER DEFAULT 1"))


async def _migrate_match_time_settings(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(match)"))
    columns = {row[1]: row for row in result.fetchall()}
    if not columns:
        return
    if "period_minutes" not in columns:
        await conn.execute(text("ALTER TABLE match ADD COLUMN period_minutes INTEGER DEFAULT 25"))
    if "total_periods" not in columns:
        await conn.execute(text("ALTER TABLE match ADD COLUMN total_periods INTEGER DEFAULT 2"))
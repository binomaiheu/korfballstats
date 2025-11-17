from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from enum import Enum
from datetime import datetime


class TeamPlayerLink(SQLModel, table=True):
    team_id: int = Field(foreign_key="team.id", primary_key=True)
    player_id: int = Field(foreign_key="player.id", primary_key=True)


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    
    players: List["Player"] = Relationship(
        back_populates="teams",
        link_model=TeamPlayerLink
    )


class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    teams: List[Team] = Relationship(
        back_populates="players",
        link_model=TeamPlayerLink
    )


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(default_factory=datetime.now) 
    team_id: int = Field(foreign_key="team.id")
    opponent_name: Optional[str] = None
    location: Optional[str] = None


class MatchLineup(SQLModel, table=True):
    match_id: int = Field(foreign_key="match.id", primary_key=True)
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    team_id: int = Field(foreign_key="team.id")


class EventType(str, Enum):
    GOAL = "goal"
    GOAL_FREE_THROW = "goal_free_throw"
    GOAL_INSIDE = "goal_inside"
    SHOT = "shot"
    FOUL = "foul"
    PENALTY = "penalty"


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    match_id: int = Field(foreign_key="match.id")
    player_id: int = Field(foreign_key="player.id")
    team_id: int = Field(foreign_key="team.id")

    type: EventType
    value: int  # +1 or -1

    timestamp: datetime = Field(default_factory=datetime.now)


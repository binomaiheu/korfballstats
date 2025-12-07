from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from enum import Enum

class ActionType(str, Enum):
    SHOT = "sht"
    KORTE_KANS = "kk"
    VRIJWORP = "vw"
    STRAFWORP = "sw"
    INLOPER = "inl"
    REBOUND = "rebound"
    ASSIST = "assist"
    STEAL = "steal"

class SexType(str, Enum):
    MALE = "m"
    FEMALE = "f"

# -- Player models
class PlayerCreate(BaseModel):
    number: int
    first_name: str
    last_name: str
    sex: SexType


class PlayerRead(PlayerCreate):
    id: int

    model_config = {
        "from_attributes": True
    }

class PlayerReadWithTeams(PlayerRead):
    teams: List["TeamRead"] = Field(default_factory=list)


# -- Team models
class TeamCreate(BaseModel):
    name: str


class TeamRead(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True 
    }

class TeamReadWithPlayers(TeamRead):
    players: List["PlayerRead"] = Field(default_factory=list)


class TeamAssignPlayer(BaseModel):
    player_id: int
    team_id: int


# -- Match models
class MatchCreate(BaseModel):
    team_id: int
    date: Optional[datetime] = None
    opponent_name: str
    location: Optional[str] = None


class MatchRead(BaseModel):
    id: int
    team: TeamRead
    opponent_name: str
    date: datetime
    location: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

# -- Event models
class Action(BaseModel):
    match_id: int
    player_id: int

    timestamp: int
    x: Optional[float] = None
    y: Optional[float] = None
    period: int
    action: ActionType
    result: Optional[bool] = False

class ActionCreate(Action):
    pass

class ActionRead(Action):
    id: int

    model_config = {
        "from_attributes": True
    }

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# -- Player models
class PlayerCreate(BaseModel):
    number: int
    first_name: str
    last_name: str


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

class MatchReadWithTeam(MatchRead):
    team: TeamRead

# -- Event models
class Event(BaseModel):
    id: int
    match_id: int
    player_id: int
    team_id: int
    type: str
    value: int

class EventCreate(BaseModel):
    match_id: int
    player_id: int
    team_id: int
    type: str
    value: int
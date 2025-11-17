from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class PlayerCreate(BaseModel):
    name: str


class PlayerRead(BaseModel):
    id: int
    name: str


class TeamCreate(BaseModel):
    name: str


class TeamRead(BaseModel):
    id: int
    name: str
    players: List[PlayerRead] = []


class TeamAssignPlayer(BaseModel):
    player_id: int
    team_id: int


class MatchCreate(BaseModel):
    team_id: int
    opponent_name: str


class MatchRead(BaseModel):
    id: int
    team_id: int
    opponent_name: str
    date: datetime

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
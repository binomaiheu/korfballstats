from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload

from typing import Union, List

from backend.auth import get_current_user
from backend.db import get_session
from backend.schema import PlaytimeForMatch, PlayerPlaytime, PlayerRead, MatchRead, TimeUpdate
from backend.models import Match, Player, MatchPlayerLink, User

from logging import getLogger

logger = getLogger('uvicorn.error')

router = APIRouter(prefix="/playtime", tags=["Playtime"], dependencies=[Depends(get_current_user)])


@router.get("/{match_id}", response_model=PlaytimeForMatch)
async def get_playtime_for_match(match_id: int, session: AsyncSession = Depends(get_session)):
    # Check if match exists
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Load match with team relationship
    stmt = (
        select(Match)
        .options(selectinload(Match.team))
        .where(Match.id == match_id)
    )
    result = await session.execute(stmt)
    match = result.scalar_one_or_none()
    
    # Get all player playtimes for this match with player data
    playtime_stmt = (
        select(MatchPlayerLink, Player)
        .join(Player, MatchPlayerLink.player_id == Player.id)
        .where(MatchPlayerLink.match_id == match_id)
    )
    playtime_result = await session.execute(playtime_stmt)
    playtime_rows = playtime_result.all()
    
    # Build player playtimes list
    player_playtimes = [
        PlayerPlaytime(
            player_id=link.player_id,
            player=PlayerRead.model_validate(player),
            time_played=link.time_played
        )
        for link, player in playtime_rows
    ]
    
    return PlaytimeForMatch(
        match_id=match_id,
        match=MatchRead.model_validate(match),
        match_time_registered_s=match.time_registered_s,
        player_playtimes=player_playtimes
    )


@router.put("/{match_id}", response_model=PlaytimeForMatch)
async def update_playtime_for_match(
    match_id: int,
    time_update: TimeUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Check if match exists and is not finalized
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Cannot update playtime for a finalized match"
        )
    if match.locked_by_user_id and match.locked_by_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is locked by another user")
    
    # Update match time
    match.time_registered_s = time_update.match_time_registered_s
    
    # Update or create player playtimes
    for player_id, time_played in time_update.player_time_registered_s.items():
        # Check if player exists
        player = await session.get(Player, player_id)
        if not player:
            raise HTTPException(
                status_code=404,
                detail=f"Player with id {player_id} not found"
            )
        
        # Get or create MatchPlayerLink
        playtime_stmt = (
            select(MatchPlayerLink)
            .where(
                MatchPlayerLink.match_id == match_id,
                MatchPlayerLink.player_id == player_id
            )
        )
        playtime_result = await session.execute(playtime_stmt)
        playtime_link = playtime_result.scalar_one_or_none()
        
        if playtime_link:
            playtime_link.time_played = time_played
        else:
            playtime_link = MatchPlayerLink(
                match_id=match_id,
                player_id=player_id,
                time_played=time_played
            )
            session.add(playtime_link)
    
    try:
        session.add(match)
        await session.commit()
        await session.refresh(match, attribute_names=["team"])
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error updating playtime in database"
        )
    
    # Return updated playtime data
    return await get_playtime_for_match(match_id, session)

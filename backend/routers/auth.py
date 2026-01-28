from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import authenticate_user, create_access_token, get_current_user
from backend.db import get_session
from backend.schema import Token, UserLogin, UserRead


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
async def login(data: UserLogin, session: AsyncSession = Depends(get_session)):
    user = await authenticate_user(session, data.username, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.username)
    return Token(access_token=token, token_type="bearer", username=user.username)


@router.get("/me", response_model=UserRead)
async def me(user=Depends(get_current_user)):
    return UserRead.model_validate(user)

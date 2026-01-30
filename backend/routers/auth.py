from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    validate_new_password,
    verify_password,
)
from backend.db import get_session
from backend.schema import ChangePassword, Token, UserLogin, UserRead


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


@router.post("/change-password", status_code=200)
async def change_password(
    data: ChangePassword,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    errors = validate_new_password(data.new_password)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors[0])

    user.hashed_password = hash_password(data.new_password)
    await session.commit()
    return {"detail": "ok"}

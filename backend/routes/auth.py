from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta, datetime

from dependencies import get_db
from schemas.auth import UserCreate, UserLogin, Token, User
from models.user import User as UserModel
from services.auth import AuthService

from pydantic import BaseModel


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=User)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли пользователь
    db_user = db.query(UserModel).filter(
        (UserModel.email == user_data.email) | 
        (UserModel.username == user_data.username)
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email или username уже заняты"
        )
    
    # Создаем нового пользователя
    hashed_password = AuthService.get_password_hash(user_data.password)
    db_user = UserModel(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    # Ищем пользователя
    user = db.query(UserModel).filter(UserModel.username == user_data.username).first()
    
    if not user or not AuthService.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь неактивен"
        )
    
    # Создаем токены
    access_token = AuthService.create_access_token(
        data={"sub": user.username}
    )
    
    refresh_token = AuthService.create_refresh_token(
        data={"sub": user.username}
    )
    
    # Сохраняем refresh token в базу
    user.refresh_token = refresh_token
    user.token_expiry = datetime.utcnow() + timedelta(days=7)
    db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    # Проверяем refresh token
    token_data = AuthService.verify_token(refresh_token, "refresh")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный refresh token"
        )
    
    # Ищем пользователя с таким refresh token
    user = db.query(UserModel).filter(
        UserModel.username == token_data.username,
        UserModel.refresh_token == refresh_token
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный refresh token"
        )
    
    # Проверяем срок действия
    if user.token_expiry < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token истек"
        )
    
    # Создаем новые токены
    new_access_token = AuthService.create_access_token(
        data={"sub": user.username}
    )
    
    new_refresh_token = AuthService.create_refresh_token(
        data={"sub": user.username}
    )
    
    # Обновляем refresh token в базе
    user.refresh_token = new_refresh_token
    user.token_expiry = datetime.utcnow() + timedelta(days=7)
    db.commit()
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )

@router.post("/logout")
async def logout(current_user: UserModel = Depends(AuthService.get_current_user), 
                db: Session = Depends(get_db)):
    current_user.refresh_token = None
    current_user.token_expiry = None
    db.commit()
    
    return {"message": "Успешный выход из системы"}
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import hashlib

from models.user import User
from schemas.auth import TokenData

try:
    from dependencies import get_db
except ImportError:
    # Если файл еще не создан, создайте его или добавьте временную реализацию
    def get_db():
        raise NotImplementedError("Создайте файл dependencies.py с функцией get_db")

from config.setting import settings

# Настройки
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class AuthService:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # Fallback to simple comparison if bcrypt fails
            import hashlib
            return hashed_password == hashlib.sha256(plain_password.encode()).hexdigest()

    @staticmethod
    def get_password_hash(password):
        try:
            # Truncate password to 72 bytes to comply with bcrypt requirements
            password_bytes = password.encode('utf-8')
            if len(password_bytes) > 72:
                password = password_bytes[:72].decode('utf-8', errors='ignore')
            else:
                password = password
            return pwd_context.hash(password)
        except Exception:
            # Fallback to simple hashing if bcrypt fails
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access"):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            token_type_check: str = payload.get("type")
            
            if username is None:
                return None
            if token_type_check != token_type:
                return None
                
            return TokenData(username=username)
        except JWTError:
            return None

    @staticmethod
    def get_current_user(
        token: str = Depends(oauth2_scheme), 
        db: Session = Depends(get_db)  # Теперь get_db импортирован
    ):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        token_data = AuthService.verify_token(token)
        if token_data is None:
            raise credentials_exception
            
        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            raise credentials_exception
            
        return user
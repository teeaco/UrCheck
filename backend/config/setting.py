from pathlib import Path

class Settings:

    BASE_DIR: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: list = ["docx"]

    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True

    SECRET_KEY: str = "your-secret-key-for-jwt-tokens-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/users.db"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
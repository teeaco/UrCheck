from pathlib import Path

class Settings:

    BASE_DIR: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: list = ["docx"]

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True

settings = Settings()
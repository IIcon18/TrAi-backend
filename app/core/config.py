from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://trai_user:trai_password@db:5432/trai_db"
    SECRET_KEY: str = "SECRET_KEY_FOR_TRAI"
    RESET_DATABASE: bool = True  # Поставьте False после первого запуска

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Разрешает дополнительные переменные


settings = Settings()
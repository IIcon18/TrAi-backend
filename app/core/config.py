# app/core/config.py
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "secret")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "secret")
    RESET_DATABASE: bool = os.getenv("RESET_DATABASE", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
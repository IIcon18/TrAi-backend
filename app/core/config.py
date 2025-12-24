from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://trai_user:trai_password@db:5432/trai_db"
    SECRET_KEY: str = "SECRET_KEY_FOR_TRAI"
    # При продакшн/обычной разработке лучше не пересоздавать БД на каждом старте
    RESET_DATABASE: bool = False
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

settings = Settings()
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from enum import Enum

class LifestyleEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    """Упрощённая регистрация — только базовые данные"""
    nickname: str
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str
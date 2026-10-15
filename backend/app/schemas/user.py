from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from app.models.user import UserRole

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.client

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = {'from_attributes': True}

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    user: UserResponse

class TokenData(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

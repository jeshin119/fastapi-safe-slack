from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import re

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
    @validator('email')
    def validate_email_format(cls, v):
        # 이메일 형식 검증
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('올바른 이메일 형식을 입력해주세요.')
        return v

class UserResponse(UserBase):
    id: int
    profile_image: Optional[str] = None
    is_email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True 
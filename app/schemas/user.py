from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import re

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('비밀번호는 8자 이상이어야 합니다.')
        
        # 비밀번호 강도 검증
        has_lower = any(c.islower() for c in v)
        has_upper = any(c.isupper() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(not c.isalnum() for c in v)
        
        if not (has_lower and has_upper and has_digit):
            raise ValueError('비밀번호는 영문 대소문자와 숫자를 포함해야 합니다.')
        
        if not has_special:
            raise ValueError('비밀번호는 특수문자를 포함해야 합니다.')
        
        return v

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
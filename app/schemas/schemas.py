from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date
from app.models.models import RequestStatus
import asyncio
from app.db.session import engine, Base
from .user import *
from .workspace import *
from .channel import *
from .message import *
from .file import *
from .auth import *

# Base schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    profile_image: Optional[str] = None
    is_email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Workspace schemas
class WorkspaceBase(BaseModel):
    name: str

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceResponse(WorkspaceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class WorkspaceJoinRequestCreate(BaseModel):
    role_name: str  # role_id → role_name
    is_contractor: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class WorkspaceJoinRequestResponse(BaseModel):
    id: int
    user_id: int
    workspace_id: int
    status: RequestStatus
    requested_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Channel schemas
class ChannelBase(BaseModel):
    name: str
    is_public: bool = True

class ChannelCreate(ChannelBase):
    workspace_name: str  # workspace_id → workspace_name

class ChannelResponse(ChannelBase):
    id: int
    workspace_id: int
    created_by: Optional[int] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ChannelJoinRequestResponse(BaseModel):
    message: str

# Message schemas
class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    user_id: int
    channel_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# File schemas
class FileBase(BaseModel):
    filename: str
    min_role_name: Optional[str] = None  # min_role_id → min_role_name
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

class FileCreate(FileBase):
    pass

class FileResponse(FileBase):
    id: int
    s3_url: str
    uploaded_by: int
    uploaded_at: datetime

    class Config:
        from_attributes = True

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    workspace_id: Optional[int] = None
    role_id: Optional[int] = None
    is_workspace_admin: Optional[bool] = None
    is_contractor: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailVerification(BaseModel):
    token: str

# Response schemas
class MessageResponse(BaseModel):
    message: str

class WorkspaceMemberResponse(BaseModel):
    id: int
    user_id: int
    workspace_id: int
    role_id: int
    is_workspace_admin: bool
    is_contractor: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    user: UserResponse
    role: dict

    class Config:
        from_attributes = True 

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(create_tables())
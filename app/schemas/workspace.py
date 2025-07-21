from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from app.models.workspace import RequestStatus
from .user import UserResponse

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
    role_id: int
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
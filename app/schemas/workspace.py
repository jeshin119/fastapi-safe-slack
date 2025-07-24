from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from app.models.workspace import RequestStatus
from .user import UserResponse

class WorkspaceBase(BaseModel):
    name: str

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceCreateRequest(BaseModel):
    workspace_name: str

class WorkspaceCreateResponse(BaseModel):
    message: str
    workspace_name: str
    start_date: date  # ⬅️ 추가

class WorkspaceResponse(WorkspaceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class WorkspaceJoinRequestCreate(BaseModel):
    invite_code: str
    role_name: str

class WorkspaceApproveRequest(BaseModel):
    request_id: int
    user_name: str
    role_name: str
    is_contractor: bool
    expires_at: Optional[datetime] = None

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
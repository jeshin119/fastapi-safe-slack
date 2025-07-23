from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ChannelBase(BaseModel):
    name: str
    is_public: bool = True

class ChannelCreate(ChannelBase):
    pass

class ChannelResponse(ChannelBase):
    id: int
    workspace_id: int
    created_by: Optional[int] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ChannelJoinRequest(BaseModel):
    workspace_name: str
    channel_name: str

class ChannelApproveRequest(BaseModel):
    workspace_name: str
    channel_name: str
    user_email: str

class ChannelJoinRequestResponse(BaseModel):
    message: str
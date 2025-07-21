from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChannelBase(BaseModel):
    name: str
    is_public: bool = True

class ChannelCreate(ChannelBase):
    workspace_id: int

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
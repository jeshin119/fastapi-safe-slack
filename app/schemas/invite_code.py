from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InviteCodeCreate(BaseModel):
    workspace_name: str
    expires_at: Optional[datetime] = None

class InviteCodeResponse(BaseModel):
    code: str
    expires_at: Optional[datetime]
    used: bool
    created_at: datetime

    class Config:
        orm_mode = True
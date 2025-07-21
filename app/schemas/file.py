from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class FileBase(BaseModel):
    filename: str
    min_role_id: Optional[int] = None
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
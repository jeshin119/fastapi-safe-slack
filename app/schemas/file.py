from pydantic import BaseModel
from typing import Optional
from datetime import date
from datetime import datetime

class FileBase(BaseModel):
    filename: str
    s3_url: str

class FileCreate(FileBase):
    min_role_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

class FileResponse(FileBase):
    id: int
    uploaded_by: str
    min_role_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True
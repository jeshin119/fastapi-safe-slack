from pydantic import BaseModel
from typing import Optional
from datetime import date
from datetime import datetime

class FileBase(BaseModel):
    filename: str

class FileCreate(FileBase):
    min_role_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

class FileResponse(FileBase):
    file_id: int
    min_role_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    uploaded_by: str
    uploaded_at: datetime

    class Config:
        from_attributes = True
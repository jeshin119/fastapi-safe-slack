from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    filename = Column(String(255))
    s3_url = Column(Text)
    min_role_id = Column(Integer, ForeignKey("roles.id"))
    valid_from = Column(Date)
    valid_to = Column(Date)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    uploaded_by_user = relationship("User", back_populates="files")
    channel = relationship("Channel", back_populates="files")
    min_role = relationship("Role") 
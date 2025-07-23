from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.workspace import RequestStatus
from sqlalchemy import Enum as SQLEnum

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_default = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    workspace = relationship("Workspace", back_populates="channels")
    created_by_user = relationship("User", back_populates="created_channels")
    members = relationship("ChannelMember", back_populates="channel")
    messages = relationship("Message", back_populates="channel")
    files = relationship("File", back_populates="channel")

class ChannelMember(Base):
    __tablename__ = "channel_members"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    status = Column(SQLEnum(RequestStatus,values_callable=lambda enum_cls: [e.value for e in enum_cls],native_enum=False,name="requeststatus"), default=RequestStatus.APPROVED)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    user = relationship("User", back_populates="channel_members")
    channel = relationship("Channel", back_populates="members") 
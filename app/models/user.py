from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    profile_image = Column(String(255))
    is_email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    workspace_members = relationship("WorkspaceMember", back_populates="user")
    workspace_join_requests = relationship("WorkspaceJoinRequest", back_populates="user")
    channel_members = relationship("ChannelMember", back_populates="user")
    messages = relationship("Message", back_populates="user")
    files = relationship("File", back_populates="uploaded_by_user")
    created_channels = relationship("Channel", back_populates="created_by_user")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    level = Column(Integer, nullable=False) 
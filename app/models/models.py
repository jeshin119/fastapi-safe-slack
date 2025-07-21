from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

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

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    members = relationship("WorkspaceMember", back_populates="workspace")
    join_requests = relationship("WorkspaceJoinRequest", back_populates="workspace")
    channels = relationship("Channel", back_populates="workspace")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_workspace_admin = Column(Boolean, default=False)
    is_contractor = Column(Boolean, default=False)
    start_date = Column(Date)
    end_date = Column(Date)
    
    # 관계
    user = relationship("User", back_populates="workspace_members")
    workspace = relationship("Workspace", back_populates="members")
    role = relationship("Role")

class WorkspaceJoinRequest(Base):
    __tablename__ = "workspace_join_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    # 관계
    user = relationship("User", back_populates="workspace_join_requests")
    workspace = relationship("Workspace", back_populates="join_requests")

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
    status = Column(Enum(RequestStatus), default=RequestStatus.APPROVED)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    user = relationship("User", back_populates="channel_members")
    channel = relationship("Channel", back_populates="members")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")

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
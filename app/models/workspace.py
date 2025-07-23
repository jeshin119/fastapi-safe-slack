from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum
from sqlalchemy import Enum as SQLEnum

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    members = relationship("WorkspaceMember", back_populates="workspace")
    channels = relationship("Channel", back_populates="workspace")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_workspace_admin = Column(Boolean, default=False)
    is_contractor = Column(Boolean, default=False)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
    # 관계
    user = relationship("User", back_populates="workspace_members")
    workspace = relationship("Workspace", back_populates="members")
    role = relationship("Role")

class WorkspaceJoinRequest(Base):
    __tablename__ = "workspace_join_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invite_code_id = Column(Integer, ForeignKey("invite_codes.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    status = Column(SQLEnum(RequestStatus,values_callable=lambda enum_cls: [e.value for e in enum_cls],native_enum=False,name="requeststatus"),
    default=RequestStatus.PENDING, nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    # 관계
    user = relationship("User", back_populates="workspace_join_requests")
    invite_code = relationship("InviteCode")
    role = relationship("Role") 
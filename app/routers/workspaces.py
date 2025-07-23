from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel, Role
from app.schemas.workspace import WorkspaceJoinRequestCreate, WorkspaceApproveRequest
from app.schemas.channel import ChannelResponse
from app.schemas.message import MessageResponse
from app.core.utils import get_current_user, get_current_user_with_context
from datetime import datetime
from typing import List
from app.models.workspace import RequestStatus
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter()

class WorkspaceRequest(BaseModel):
    workspace_name: str

class WorkspaceJoinRequestList(BaseModel):
    request_id: int
    user_email: str
    user_name: str
    role_name: str
    is_contractor: bool = False
    requested_at: datetime

class WorkspaceMemberList(BaseModel):
    user_id: int
    name: str
    email: str
    role_name: str

@router.post("/join-request")
async def request_workspace_join(
    request_data: WorkspaceJoinRequestCreate,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 이미 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    
    # role_name으로 role_id 찾기
    result = await db.execute(select(Role).where(Role.name == request_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )
    
    # 기존 요청 확인
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.user_id == user_context["user_id"],
        WorkspaceJoinRequest.workspace_id == workspace.id,
        WorkspaceJoinRequest.status == "pending"
    ))
    existing_request = result.scalars().first()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 참여 요청이 대기 중입니다."
        )
    
    join_request = WorkspaceJoinRequest(
        user_id=user_context["user_id"],
        workspace_id=workspace.id
    )
    db.add(join_request)
    await db.commit()
    return {
        "message": "워크스페이스 가입 요청이 전송되었습니다."
    }

@router.post("/join-requests-list")
async def get_workspace_join_requests(
    workspace_data: WorkspaceRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 현재 사용자가 워크스페이스 관리자인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 요청 목록을 볼 수 있습니다."
        )
    
    # 가입 요청 목록 조회
    result = await db.execute(
        select(WorkspaceJoinRequest, User, Role)
        .join(User, WorkspaceJoinRequest.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .where(
            WorkspaceJoinRequest.workspace_id == workspace.id,
            WorkspaceJoinRequest.status == "pending"
        )
    )
    requests_data = result.all()
    
    return [
        {
            "request_id": request.id,
            "user_email": user.email,
            "user_name": user.name,
            "role_name": role.name,
            "is_contractor": False,  # 기본값
            "requested_at": request.created_at
        }
        for request, user, role in requests_data
    ]

@router.post("/approve")
async def approve_workspace_join(
    approve_data: WorkspaceApproveRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == approve_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 현재 사용자가 워크스페이스 관리자인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )
    
    # user_name으로 사용자 찾기
    result = await db.execute(select(User).where(User.name == approve_data.user_name))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # role_name으로 role_id 찾기
    result = await db.execute(select(Role).where(Role.name == approve_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )
    
    # 대기 중인 요청 확인
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.user_id == target_user.id,
        WorkspaceJoinRequest.workspace_id == workspace.id,
        WorkspaceJoinRequest.status == "pending"
    ))
    join_request = result.scalars().first()
    if not join_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 가입 요청을 찾을 수 없습니다."
        )
    
    # 워크스페이스 멤버로 추가
    member = WorkspaceMember(
        user_id=target_user.id,
        workspace_id=workspace.id,
        role_id=role.id,
        is_workspace_admin=False,
        is_contractor=approve_data.is_contractor
    )
    db.add(member)
    
    # 요청 상태를 승인으로 변경
    join_request.status = "approved"
    
    await db.commit()
    return {
        "message": "사용자가 워크스페이스에 추가되었습니다."
    }

@router.post("/members")
async def get_workspace_members(
    workspace_data: WorkspaceRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 현재 사용자가 워크스페이스 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 워크스페이스 멤버 정보 조회 (JOIN으로 한 번에 가져오기)
    result = await db.execute(
        select(WorkspaceMember, User, Role)
        .join(User, WorkspaceMember.user_id == User.id)
        .join(Role, WorkspaceMember.role_id == Role.id)
        .where(WorkspaceMember.workspace_id == workspace.id)
    )
    members_data = result.all()
    
    return [
        {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "role_name": role.name
        }
        for member, user, role in members_data
    ] 
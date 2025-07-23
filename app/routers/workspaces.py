from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel, Role
from app.schemas.workspace import WorkspaceJoinRequestCreate, WorkspaceApproveRequest, WorkspaceCreateRequest, WorkspaceCreateResponse
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

@router.post("/create")
async def create_workspace(
    request_data: WorkspaceCreateRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 워크스페이스 이름 중복 확인
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    existing_workspace = result.scalars().first()
    if existing_workspace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 워크스페이스 이름입니다."
        )
    
    # 워크스페이스 생성
    new_workspace = Workspace(name=request_data.workspace_name)
    db.add(new_workspace)
    await db.flush()  # ID를 얻기 위해 flush
    
    # 기본 관리자 역할 찾기 (level이 가장 높은 역할)
    result = await db.execute(select(Role).order_by(Role.level.desc()))
    admin_role = result.scalars().first()
    
    if not admin_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템에 역할이 설정되지 않았습니다."
        )
    
    # 생성자를 워크스페이스 관리자로 추가
    workspace_member = WorkspaceMember(
        user_id=user_context["user_id"],
        workspace_id=new_workspace.id,
        role_id=admin_role.id,
        is_workspace_admin=True
    )
    db.add(workspace_member)
    
    await db.commit()
    
    return WorkspaceCreateResponse(
        message="워크스페이스가 생성되었습니다.",
        workspace_name=request_data.workspace_name
    )

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
    # 가입 요청 찾기 (request_id)
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.id == approve_data.request_id,
        WorkspaceJoinRequest.status == "pending"
    ))
    join_request = result.scalars().first()
    if not join_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 가입 요청을 찾을 수 없습니다."
        )
    
    # 워크스페이스 관리자 권한 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == join_request.workspace_id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )
    
    # 역할 찾기
    result = await db.execute(select(Role).where(Role.name == approve_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )
    
    # 이미 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == join_request.user_id,
        WorkspaceMember.workspace_id == join_request.workspace_id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    
    # 멤버로 추가
    member = WorkspaceMember(
        user_id=join_request.user_id,
        workspace_id=join_request.workspace_id,
        role_id=role.id,
        is_workspace_admin=False,
        is_contractor=approve_data.is_contractor,
        end_date=approve_data.expires_at
    )
    db.add(member)
    
    # 요청 상태를 승인으로 변경
    join_request.status = "approved"
    join_request.processed_at = datetime.utcnow()
    
    await db.commit()
    return {"message": "사용자가 워크스페이스에 추가되었습니다."}

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
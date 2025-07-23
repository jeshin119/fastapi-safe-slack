from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel, Role
from app.schemas.workspace import WorkspaceJoinRequestCreate, WorkspaceApproveRequest
from app.schemas.channel import ChannelResponse
from app.schemas.message import MessageResponse
from app.core.utils import get_current_user, get_current_user_with_context, check_user_permission_by_name
from datetime import datetime
from typing import List
from app.models.workspace import RequestStatus
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/join-request")
async def request_workspace_join(
    request_data: WorkspaceJoinRequestCreate,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 확인 (이미 멤버인지 체크)
    if user_context.get("workspace_name") == request_data.workspace_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # role_name으로 role_id 찾기
    result = await db.execute(select(Role).where(Role.name == request_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )
    
    # 기존 요청 확인 (토큰에서 user_id 사용)
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
        "message": "요청이 전송되었습니다. 관리자의 승인을 기다리세요."
    }

@router.post("/approve")
async def approve_workspace_join(
    approve_data: WorkspaceApproveRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        approve_data.workspace_name, 
        require_admin=True
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == approve_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # user_email로 사용자 찾기
    result = await db.execute(select(User).where(User.email == approve_data.user_email))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 자기 자신을 승인하려는 경우 체크
    if target_user.email == user_context["user_email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신을 승인할 수 없습니다."
        )
    
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
    
    join_request.status = "approved"
    now = datetime.now()
    join_request.processed_at = now
    
    # 기본 직급(사원) 찾기
    result = await db.execute(select(Role).where(Role.name == "사원"))
    default_role = result.scalars().first()
    if not default_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="기본 직급을 찾을 수 없습니다."
        )
    
    member = WorkspaceMember(
        user_id=target_user.id,
        workspace_id=workspace.id,
        role_id=default_role.id,
        is_workspace_admin=False,
        is_contractor=False,
        start_date=now,
        end_date=(now + timedelta(days=7))
    )
    db.add(member)
    
    # 기본 채널에 자동 추가
    result = await db.execute(select(Channel).where(
        Channel.workspace_id == workspace.id,
        Channel.is_default == True
    ))
    default_channel = result.scalars().first()
    if default_channel:
        from app.models.models import ChannelMember
        channel_member = ChannelMember(
            user_id=target_user.id,
            channel_id=default_channel.id,
            status="approved"
        )
        db.add(channel_member)
    
    await db.commit()
    return {
        "message": "사용자가 워크스페이스에 추가되었습니다."
    }

@router.get("/{workspace_name}/channels")
async def get_workspace_channels(
    workspace_name: str,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    result = await db.execute(select(Channel).where(Channel.workspace_id == workspace.id))
    channels = result.scalars().all()
    
    # 채널 생성자 정보를 한 번에 가져오기 (성능 최적화)
    creator_ids = list(set(channel.created_by for channel in channels if channel.created_by))
    creators = {}
    if creator_ids:
        result = await db.execute(select(User).where(User.id.in_(creator_ids)))
        users = result.scalars().all()
        creators = {user.id: user.name for user in users}
    
    return [
        {
            "name": channel.name,
            "is_public": channel.is_public,
            "created_by": creators.get(channel.created_by, "Unknown") if channel.created_by else "Unknown",
            "is_default": channel.is_default,
            "created_at": channel.created_at
        }
        for channel in channels
    ]

@router.get("/{workspace_name}/members")
async def get_workspace_members(
    workspace_name: str,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
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
            "user_email": user.email,
            "user_name": user.name,
            "role_name": role.name,
            "is_workspace_admin": member.is_workspace_admin,
            "is_contractor": member.is_contractor,
            "start_date": member.start_date,
            "end_date": member.end_date
        }
        for member, user, role in members_data
    ] 
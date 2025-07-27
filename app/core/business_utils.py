from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import Workspace, WorkspaceMember, WorkspaceJoinRequest, InviteCode, Role, User, Channel, ChannelMember
from app.core.db_utils import get_workspace_by_name, get_role_by_name
from app.core.permission_utils import verify_workspace_access, verify_workspace_admin, check_user_permission
from app.core.exception_utils import raise_duplicate_workspace, raise_internal_server_error, raise_not_found
from app.core.date_utils import get_current_date
from typing import List, Optional, Dict
from datetime import datetime


async def create_workspace_with_admin(db: AsyncSession, workspace_name: str, user_id: int) -> Dict:
    """
    워크스페이스 생성 및 관리자 설정
    """
    # 워크스페이스 이름 중복 확인
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
    existing_workspace = result.scalars().first()
    if existing_workspace:
        raise_duplicate_workspace()
    
    # 워크스페이스 생성
    new_workspace = Workspace(name=workspace_name)
    db.add(new_workspace)
    await db.flush()
    
    # 기본 관리자 역할 찾기
    result = await db.execute(select(Role).order_by(Role.level.desc()))
    admin_role = result.scalars().first()
    
    if not admin_role:
        raise_internal_server_error("시스템에 역할이 설정되지 않았습니다.")
    
    today = get_current_date()
    
    # 생성자를 워크스페이스 관리자로 추가
    workspace_member = WorkspaceMember(
        user_id=user_id,
        workspace_id=new_workspace.id,
        role_id=admin_role.id,
        is_workspace_admin=True,
        start_date=today
    )
    db.add(workspace_member)
    
    await db.commit()
    
    return {
        "message": "워크스페이스가 생성되었습니다.",
        "workspace_name": workspace_name,
        "start_date": today
    }


async def get_workspace_join_requests_for_admin(db: AsyncSession, workspace_name: str, user_id: int) -> List[Dict]:
    """
    관리자를 위한 워크스페이스 가입 요청 목록 조회
    """
    # 워크스페이스 접근 권한 및 관리자 권한 확인
    workspace = await verify_workspace_access(db, user_id, workspace_name)
    await verify_workspace_admin(db, user_id, workspace.id)
    
    # 해당 워크스페이스의 초대 코드 목록 조회
    result = await db.execute(select(InviteCode).where(InviteCode.workspace_id == workspace.id))
    invite_codes = result.scalars().all()
    invite_code_ids = [ic.id for ic in invite_codes]
    
    if not invite_code_ids:
        return []
    
    # 가입 요청 조회
    result = await db.execute(
        select(WorkspaceJoinRequest, User, Role)
        .join(User, WorkspaceJoinRequest.user_id == User.id)
        .join(Role, WorkspaceJoinRequest.role_id == Role.id)
        .where(
            WorkspaceJoinRequest.invite_code_id.in_(invite_code_ids),
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
            "is_contractor": False,
            "requested_at": request.requested_at
        }
        for request, user, role in requests_data
    ]


async def get_user_workspaces_with_member_count(db: AsyncSession, user_id: int) -> List[Dict]:
    """
    사용자의 워크스페이스 목록 조회 (멤버 수 포함)
    """
    result = await db.execute(
        select(Workspace, WorkspaceMember, Role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .join(Role, WorkspaceMember.role_id == Role.id)
        .where(WorkspaceMember.user_id == user_id)
    )
    
    workspaces_data = result.all()
    
    return [
        {
            "name": workspace.name,
            "role_id": role.id,
            "member_count": await _get_workspace_member_count(db, workspace.id),
            "start_date": membership.start_date,
            "is_workspace_admin": membership.is_workspace_admin
        }
        for workspace, membership, role in workspaces_data
    ]


async def create_channel_with_creator(db: AsyncSession, workspace_name: str, channel_name: str, user_id: int) -> Dict:
    """
    채널 생성 및 생성자 설정
    """
    # 워크스페이스 접근 권한 확인
    workspace = await verify_workspace_access(db, user_id, workspace_name)
    
    # 채널 이름 중복 확인
    result = await db.execute(
        select(Channel).where(
            Channel.name == channel_name,
            Channel.workspace_id == workspace.id
        )
    )
    existing_channel = result.scalars().first()
    if existing_channel:
        raise_duplicate_channel()
    
    # 채널 생성
    new_channel = Channel(
        name=channel_name,
        workspace_id=workspace.id,
        creator_id=user_id
    )
    db.add(new_channel)
    await db.flush()
    
    # 생성자를 채널 멤버로 추가
    channel_member = ChannelMember(
        user_id=user_id,
        channel_id=new_channel.id,
        joined_at=datetime.now()
    )
    db.add(channel_member)
    
    await db.commit()
    
    return {
        "message": "채널이 생성되었습니다.",
        "channel_name": channel_name,
        "workspace_name": workspace_name
    }


async def _get_workspace_member_count(db: AsyncSession, workspace_id: int) -> int:
    """
    워크스페이스 멤버 수 조회 (내부 함수)
    """
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    return len(result.scalars().all())


def raise_duplicate_channel():
    """채널 중복 예외 발생"""
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="이미 존재하는 채널명입니다."
    ) 
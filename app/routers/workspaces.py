from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel
from app.schemas.workspace import WorkspaceJoinRequestCreate
from app.schemas.channel import ChannelResponse
from app.schemas.message import MessageResponse
from app.core.utils import get_current_user, check_user_permission
from datetime import datetime
from typing import List

router = APIRouter()

@router.post("/{workspace_id}/join-request", response_model=MessageResponse)
async def request_workspace_join(
    workspace_id: int,
    request_data: WorkspaceJoinRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.user_id == current_user.id,
        WorkspaceJoinRequest.workspace_id == workspace_id,
        WorkspaceJoinRequest.status == "pending"
    ))
    existing_request = result.scalars().first()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 참여 요청이 대기 중입니다."
        )
    join_request = WorkspaceJoinRequest(
        user_id=current_user.id,
        workspace_id=workspace_id
    )
    db.add(join_request)
    await db.commit()
    return {"message": "요청이 전송되었습니다. 관리자의 승인을 기다리세요."}

@router.post("/{workspace_id}/approve/{user_id}", response_model=MessageResponse)
async def approve_workspace_join(
    workspace_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    current_membership = result.scalars().first()
    if not current_membership or not current_membership.is_workspace_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.user_id == user_id,
        WorkspaceJoinRequest.workspace_id == workspace_id,
        WorkspaceJoinRequest.status == "pending"
    ))
    join_request = result.scalars().first()
    if not join_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 가입 요청을 찾을 수 없습니다."
        )
    join_request.status = "approved"
    join_request.processed_at = datetime.now()
    member = WorkspaceMember(
        user_id=user_id,
        workspace_id=workspace_id,
        role_id=1,  # 기본 직급 (사원)
        is_workspace_admin=False,
        is_contractor=False
    )
    db.add(member)
    result = await db.execute(select(Channel).where(
        Channel.workspace_id == workspace_id,
        Channel.is_default == True
    ))
    default_channel = result.scalars().first()
    if default_channel:
        from app.models.models import ChannelMember
        channel_member = ChannelMember(
            user_id=user_id,
            channel_id=default_channel.id,
            status="approved"
        )
        db.add(channel_member)
    await db.commit()
    return {"message": "사용자가 워크스페이스에 추가되었습니다."}

@router.get("/{workspace_id}/channels")
async def get_workspace_channels(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    result = await db.execute(select(Channel).where(Channel.workspace_id == workspace_id))
    channels = result.scalars().all()
    return [
        {
            "id": channel.id,
            "name": channel.name,
            "is_public": channel.is_public
        }
        for channel in channels
    ] 
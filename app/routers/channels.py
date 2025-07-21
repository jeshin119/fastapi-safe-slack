from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Channel, ChannelMember, WorkspaceMember
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelJoinRequestResponse
from app.core.utils import get_current_user, check_user_permission
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=ChannelResponse)
async def create_channel(
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel_data.workspace_id
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    result = await db.execute(select(Channel).where(
        Channel.name == channel_data.name,
        Channel.workspace_id == channel_data.workspace_id
    ))
    existing_channel = result.scalars().first()
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 채널명입니다."
        )
    channel = Channel(
        name=channel_data.name,
        workspace_id=channel_data.workspace_id,
        created_by=current_user.id,
        is_public=channel_data.is_public
    )
    db.add(channel)
    await db.flush()
    if channel_data.is_public:
        member = ChannelMember(
            user_id=current_user.id,
            channel_id=channel.id,
            status="approved"
        )
        db.add(member)
    await db.commit()
    await db.refresh(channel)
    return channel

@router.post("/{channel_id}/join-request", response_model=ChannelJoinRequestResponse)
async def request_channel_join(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel.workspace_id
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    if channel.is_public:
        result = await db.execute(select(ChannelMember).where(
            ChannelMember.user_id == current_user.id,
            ChannelMember.channel_id == channel_id
        ))
        existing_member = result.scalars().first()
        if not existing_member:
            member = ChannelMember(
                user_id=current_user.id,
                channel_id=channel_id,
                status="approved"
            )
            db.add(member)
            await db.commit()
        return {"message": "채널에 입장했습니다."}
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        if existing_member.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 채널 멤버입니다."
            )
        elif existing_member.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 입장 요청이 대기 중입니다."
            )
    member = ChannelMember(
        user_id=current_user.id,
        channel_id=channel_id,
        status="pending"
    )
    db.add(member)
    await db.commit()
    return {"message": "채널 관리자에게 입장 요청이 전송되었습니다."}

@router.post("/{channel_id}/approve/{user_id}", response_model=ChannelJoinRequestResponse)
async def approve_channel_join(
    channel_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "approved"
    ))
    current_membership = result.scalars().first()
    if not current_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "pending"
    ))
    target_membership = result.scalars().first()
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 입장 요청을 찾을 수 없습니다."
        )
    target_membership.status = "approved"
    await db.commit()
    return {"message": "채널 입장이 승인되었습니다."} 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Workspace, Channel, WorkspaceMember, ChannelMember, User, Role
from fastapi import HTTPException, status
from typing import Optional, Tuple


async def get_workspace_by_name(db: AsyncSession, workspace_name: str) -> Workspace:
    """
    워크스페이스 이름으로 워크스페이스를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        workspace_name: 워크스페이스 이름
        
    Returns:
        Workspace: 워크스페이스 객체
        
    Raises:
        HTTPException: 워크스페이스를 찾을 수 없는 경우
    """
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    return workspace


async def get_channel_by_name(db: AsyncSession, channel_name: str, workspace_id: int) -> Channel:
    """
    채널 이름과 워크스페이스 ID로 채널을 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        channel_name: 채널 이름
        workspace_id: 워크스페이스 ID
        
    Returns:
        Channel: 채널 객체
        
    Raises:
        HTTPException: 채널을 찾을 수 없는 경우
    """
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace_id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    return channel


async def get_workspace_membership(db: AsyncSession, user_id: int, workspace_id: int) -> Optional[WorkspaceMember]:
    """
    사용자의 워크스페이스 멤버십을 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        workspace_id: 워크스페이스 ID
        
    Returns:
        WorkspaceMember: 워크스페이스 멤버십 객체 (없으면 None)
    """
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    return result.scalars().first()


async def get_channel_membership(db: AsyncSession, user_id: int, channel_id: int, status: str = "approved") -> Optional[ChannelMember]:
    """
    사용자의 채널 멤버십을 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        channel_id: 채널 ID
        status: 멤버십 상태 (기본값: "approved")
        
    Returns:
        ChannelMember: 채널 멤버십 객체 (없으면 None)
    """
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == status
    ))
    return result.scalars().first()


async def get_user_role(db: AsyncSession, role_id: int) -> Optional[Role]:
    """
    역할 ID로 역할 정보를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        role_id: 역할 ID
        
    Returns:
        Role: 역할 객체 (없으면 None)
    """
    result = await db.execute(select(Role).where(Role.id == role_id))
    return result.scalars().first()


async def get_workspace_and_channel(db: AsyncSession, workspace_name: str, channel_name: str) -> Tuple[Workspace, Channel]:
    """
    워크스페이스와 채널을 한 번에 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        workspace_name: 워크스페이스 이름
        channel_name: 채널 이름
        
    Returns:
        Tuple[Workspace, Channel]: 워크스페이스와 채널 객체
        
    Raises:
        HTTPException: 워크스페이스나 채널을 찾을 수 없는 경우
    """
    workspace = await get_workspace_by_name(db, workspace_name)
    channel = await get_channel_by_name(db, channel_name, workspace.id)
    return workspace, channel


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    사용자 ID로 사용자 정보를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        
    Returns:
        User: 사용자 객체 (없으면 None)
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def get_role_by_name(db: AsyncSession, role_name: str) -> Optional[Role]:
    """
    역할 이름으로 역할 정보를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        role_name: 역할 이름
        
    Returns:
        Role: 역할 객체 (없으면 None)
    """
    result = await db.execute(select(Role).where(Role.name == role_name))
    return result.scalars().first() 
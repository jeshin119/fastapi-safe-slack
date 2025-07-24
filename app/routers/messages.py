from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Message, Channel, ChannelMember, Workspace
from app.schemas.message import MessageCreate, MessageResponse
from app.core.utils import get_current_user, get_current_user_with_context, check_user_permission_by_name
from typing import List

router = APIRouter()

@router.post("/{channel_name}/messages", response_model=MessageResponse)
async def create_message(
    channel_name: str,
    message_data: MessageCreate,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
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
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 메시지를 보낼 권한이 없습니다."
        )
    
    message = Message(
        channel_id=channel.id,
        user_id=user_context["user_id"],  # 토큰에서 user_id 사용
        content=message_data.content
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    return {
        "user_email": user_context["user_email"],  # 토큰에서 user_email 사용
        "channel_name": channel_name,
        "content": message.content,
        "created_at": message.created_at
    }

@router.get("/{channel_name}/messages", response_model=List[MessageResponse])
async def get_messages(
    channel_name: str,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
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
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 메시지 조회
    result = await db.execute(select(Message).where(Message.channel_id == channel.id).order_by(Message.created_at.desc()))
    messages = result.scalars().all()
    
    # 사용자 정보를 한 번에 가져오기 (성능 최적화)
    user_ids = list(set(message.user_id for message in messages))
    users = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        user_list = result.scalars().all()
        users = {user.id: user.email for user in user_list}
    
    return [
        {
            "user_email": users.get(message.user_id, "Unknown"),
            "content": message.content,
            "created_at": message.created_at
        }
        for message in messages
    ]

@router.get("/{channel_name}/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    channel_name: str,
    message_id: int,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
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
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 특정 메시지 조회
    result = await db.execute(select(Message).where(
        Message.id == message_id,
        Message.channel_id == channel.id
    ))
    message = result.scalars().first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="메시지를 찾을 수 없습니다."
        )
    
    # 메시지 작성자 정보 조회
    result = await db.execute(select(User).where(User.id == message.user_id))
    user = result.scalars().first()
    
    return {
        "user_email": user.email if user else "Unknown",
        "content": message.content,
        "created_at": message.created_at
    }

@router.put("/{channel_name}/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    channel_name: str,
    message_id: int,
    message_data: MessageCreate,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
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
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 특정 메시지 조회
    result = await db.execute(select(Message).where(
        Message.id == message_id,
        Message.channel_id == channel.id
    ))
    message = result.scalars().first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="메시지를 찾을 수 없습니다."
        )
    
    # 메시지 작성자 확인 (토큰에서 user_id 사용)
    if message.user_id != user_context["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자신이 작성한 메시지만 수정할 수 있습니다."
        )
    
    # 메시지 수정
    message.content = message_data.content
    await db.commit()
    await db.refresh(message)
    
    return {
        "user_email": user_context["user_email"],  # 토큰에서 user_email 사용
        "content": message.content,
        "created_at": message.created_at
    }

@router.delete("/{channel_name}/messages/{message_id}")
async def delete_message(
    channel_name: str,
    message_id: int,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
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
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 특정 메시지 조회
    result = await db.execute(select(Message).where(
        Message.id == message_id,
        Message.channel_id == channel.id
    ))
    message = result.scalars().first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="메시지를 찾을 수 없습니다."
        )
    
    # 메시지 작성자 확인 (토큰에서 user_id 사용)
    if message.user_id != user_context["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자신이 작성한 메시지만 삭제할 수 있습니다."
        )
    
    # 메시지 삭제
    await db.delete(message)
    await db.commit()
    
    return {"message": "메시지가 삭제되었습니다."} 
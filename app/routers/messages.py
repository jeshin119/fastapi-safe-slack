from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, Message, Channel, ChannelMember
from app.schemas.message import MessageCreate, MessageResponse
from app.core.utils import get_current_user
from typing import List

router = APIRouter()

@router.post("/{channel_id}/messages", response_model=MessageResponse)
async def create_message(
    channel_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """채널에 메시지 전송"""
    
    # 채널 존재 확인
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 사용자가 채널 멤버인지 확인
    membership = db.query(ChannelMember).filter(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "approved"
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 메시지를 보낼 권한이 없습니다."
        )
    
    # 메시지 생성
    message = Message(
        channel_id=channel_id,
        user_id=current_user.id,
        content=message_data.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return message

@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """채널의 메시지 목록 조회"""
    
    # 채널 존재 확인
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 사용자가 채널 멤버인지 확인
    membership = db.query(ChannelMember).filter(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "approved"
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 메시지 목록 조회 (최신순)
    messages = db.query(Message).filter(
        Message.channel_id == channel_id
    ).order_by(Message.created_at.desc()).all()
    
    return messages 
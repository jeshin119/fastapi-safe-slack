from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Channel, ChannelMember, WorkspaceMember
from app.schemas import ChannelCreate, ChannelResponse, ChannelJoinRequestResponse
from app.core.utils import get_current_user, check_user_permission
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=ChannelResponse)
async def create_channel(
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """채널 생성"""
    
    # 워크스페이스 멤버십 확인
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel_data.workspace_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 채널명 중복 확인
    existing_channel = db.query(Channel).filter(
        Channel.name == channel_data.name,
        Channel.workspace_id == channel_data.workspace_id
    ).first()
    
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 채널명입니다."
        )
    
    # 채널 생성
    channel = Channel(
        name=channel_data.name,
        workspace_id=channel_data.workspace_id,
        created_by=current_user.id,
        is_public=channel_data.is_public
    )
    db.add(channel)
    db.flush()
    
    # 공개 채널인 경우 생성자를 자동으로 멤버로 추가
    if channel_data.is_public:
        member = ChannelMember(
            user_id=current_user.id,
            channel_id=channel.id,
            status="approved"
        )
        db.add(member)
    
    db.commit()
    db.refresh(channel)
    
    return channel

@router.post("/{channel_id}/join-request", response_model=ChannelJoinRequestResponse)
async def request_channel_join(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """비공개 채널 입장 요청"""
    
    # 채널 존재 확인
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 워크스페이스 멤버십 확인
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel.workspace_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 공개 채널인 경우 자동으로 멤버로 추가
    if channel.is_public:
        existing_member = db.query(ChannelMember).filter(
            ChannelMember.user_id == current_user.id,
            ChannelMember.channel_id == channel_id
        ).first()
        
        if not existing_member:
            member = ChannelMember(
                user_id=current_user.id,
                channel_id=channel_id,
                status="approved"
            )
            db.add(member)
            db.commit()
        
        return {"message": "채널에 입장했습니다."}
    
    # 비공개 채널인 경우
    existing_member = db.query(ChannelMember).filter(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id
    ).first()
    
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
    
    # 입장 요청 생성
    member = ChannelMember(
        user_id=current_user.id,
        channel_id=channel_id,
        status="pending"
    )
    db.add(member)
    db.commit()
    
    return {"message": "채널 관리자에게 입장 요청이 전송되었습니다."}

@router.post("/{channel_id}/approve/{user_id}", response_model=ChannelJoinRequestResponse)
async def approve_channel_join(
    channel_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """비공개 채널 입장 승인"""
    
    # 채널 존재 확인
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 현재 사용자가 채널 멤버인지 확인
    current_membership = db.query(ChannelMember).filter(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "approved"
    ).first()
    
    if not current_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 승인할 사용자의 요청 찾기
    target_membership = db.query(ChannelMember).filter(
        ChannelMember.user_id == user_id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "pending"
    ).first()
    
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 입장 요청을 찾을 수 없습니다."
        )
    
    # 요청을 승인으로 변경
    target_membership.status = "approved"
    db.commit()
    
    return {"message": "채널 입장이 승인되었습니다."} 
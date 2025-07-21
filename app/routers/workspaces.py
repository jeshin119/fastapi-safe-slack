from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel
from app.schemas import WorkspaceJoinRequestCreate, MessageResponse
from app.core.utils import get_current_user, check_user_permission
from datetime import datetime
from typing import List

router = APIRouter()

@router.post("/{workspace_id}/join-request", response_model=MessageResponse)
async def request_workspace_join(
    workspace_id: int,
    request_data: WorkspaceJoinRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """워크스페이스 참여 요청"""
    
    # 워크스페이스 존재 확인
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 이미 멤버인지 확인
    existing_member = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    
    # 이미 요청한 상태인지 확인
    existing_request = db.query(WorkspaceJoinRequest).filter(
        WorkspaceJoinRequest.user_id == current_user.id,
        WorkspaceJoinRequest.workspace_id == workspace_id,
        WorkspaceJoinRequest.status == "pending"
    ).first()
    
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 참여 요청이 대기 중입니다."
        )
    
    # 워크스페이스 가입 요청 생성
    join_request = WorkspaceJoinRequest(
        user_id=current_user.id,
        workspace_id=workspace_id
    )
    db.add(join_request)
    db.commit()
    
    return {"message": "요청이 전송되었습니다. 관리자의 승인을 기다리세요."}

@router.post("/{workspace_id}/approve/{user_id}", response_model=MessageResponse)
async def approve_workspace_join(
    workspace_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """워크스페이스 요청 승인 (관리자만 가능)"""
    
    # 워크스페이스 존재 확인
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 현재 사용자가 관리자인지 확인
    current_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ).first()
    
    if not current_membership or not current_membership.is_workspace_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )
    
    # 승인할 사용자 확인
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 가입 요청 찾기
    join_request = db.query(WorkspaceJoinRequest).filter(
        WorkspaceJoinRequest.user_id == user_id,
        WorkspaceJoinRequest.workspace_id == workspace_id,
        WorkspaceJoinRequest.status == "pending"
    ).first()
    
    if not join_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 가입 요청을 찾을 수 없습니다."
        )
    
    # 요청 상태를 승인으로 변경
    join_request.status = "approved"
    join_request.processed_at = datetime.now()
    
    # 워크스페이스 멤버로 추가
    member = WorkspaceMember(
        user_id=user_id,
        workspace_id=workspace_id,
        role_id=1,  # 기본 직급 (사원)
        is_workspace_admin=False,
        is_contractor=False
    )
    db.add(member)
    
    # 기본 채널에 자동 추가
    default_channel = db.query(Channel).filter(
        Channel.workspace_id == workspace_id,
        Channel.is_default == True
    ).first()
    
    if default_channel:
        from app.models import ChannelMember
        channel_member = ChannelMember(
            user_id=user_id,
            channel_id=default_channel.id,
            status="approved"
        )
        db.add(channel_member)
    
    db.commit()
    
    return {"message": "사용자가 워크스페이스에 추가되었습니다."}

@router.get("/{workspace_id}/channels")
async def get_workspace_channels(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """워크스페이스의 채널 목록 조회"""
    
    # 워크스페이스 존재 확인
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 사용자가 워크스페이스 멤버인지 확인
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 채널 목록 조회
    channels = db.query(Channel).filter(Channel.workspace_id == workspace_id).all()
    
    return [
        {
            "id": channel.id,
            "name": channel.name,
            "is_public": channel.is_public
        }
        for channel in channels
    ] 
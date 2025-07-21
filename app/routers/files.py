from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, File as FileModel, Channel, ChannelMember, WorkspaceMember, Role
from app.schemas.file import FileResponse
from app.core.utils import get_current_user
from typing import List, Optional
from datetime import date
import boto3
import os
from app.core.config import settings

router = APIRouter()

def upload_to_s3(file: UploadFile, filename: str) -> str:
    """S3에 파일 업로드 (실제 구현에서는 S3 설정 필요)"""
    # 실제 S3 업로드 로직은 여기에 구현
    # 여기서는 임시로 로컬 경로를 반환
    return f"https://s3.amazonaws.com/{settings.S3_BUCKET_NAME}/{filename}"

@router.post("/{channel_id}/files", response_model=FileResponse)
async def upload_file(
    channel_id: int,
    file: UploadFile = File(...),
    min_role_id: Optional[int] = Form(None),
    valid_from: Optional[str] = Form(None),
    valid_to: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """파일 업로드"""
    
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
            detail="채널에 파일을 업로드할 권한이 없습니다."
        )
    
    # 파일 크기 제한 (10MB)
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 크기는 10MB를 초과할 수 없습니다."
        )
    
    # 허용된 파일 형식 확인
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 파일 형식입니다."
        )
    
    # S3에 파일 업로드
    s3_url = upload_to_s3(file, file.filename)
    
    # 날짜 파싱
    valid_from_date = None
    valid_to_date = None
    
    if valid_from:
        try:
            valid_from_date = date.fromisoformat(valid_from)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 시작 날짜 형식입니다."
            )
    
    if valid_to:
        try:
            valid_to_date = date.fromisoformat(valid_to)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 종료 날짜 형식입니다."
            )
    
    # 데이터베이스에 파일 정보 저장
    file_record = FileModel(
        uploaded_by=current_user.id,
        channel_id=channel_id,
        filename=file.filename,
        s3_url=s3_url,
        min_role_id=min_role_id,
        valid_from=valid_from_date,
        valid_to=valid_to_date
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)
    
    return file_record

@router.get("/{channel_id}/files", response_model=List[FileResponse])
async def get_files(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """채널의 파일 목록 조회 (권한 포함)"""
    
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
    
    # 사용자의 워크스페이스 정보 가져오기
    workspace_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel.workspace_id
    ).first()
    
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 사용자의 직급 정보 가져오기
    user_role = db.query(Role).filter(Role.id == workspace_membership.role_id).first()
    user_role_level = user_role.level if user_role else 0
    
    # 계약직인 경우 기간 확인
    today = date.today()
    if workspace_membership.is_contractor:
        if workspace_membership.start_date and today < workspace_membership.start_date:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="계약 기간이 시작되지 않았습니다."
            )
        if workspace_membership.end_date and today > workspace_membership.end_date:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="계약 기간이 종료되었습니다."
            )
    
    # 파일 목록 조회 (권한 및 날짜 필터링)
    files_query = db.query(FileModel).filter(FileModel.channel_id == channel_id)
    
    # 관리자가 아닌 경우 권한 필터링
    if not workspace_membership.is_workspace_admin:
        files_query = files_query.filter(
            (FileModel.min_role_id.is_(None)) |  # 권한 제한이 없는 파일
            (FileModel.min_role_id <= user_role_level)  # 사용자 직급 이상
        )
    
    # 날짜 필터링
    files_query = files_query.filter(
        (FileModel.valid_from.is_(None)) | (FileModel.valid_from <= today)
    ).filter(
        (FileModel.valid_to.is_(None)) | (FileModel.valid_to >= today)
    )
    
    files = files_query.all()
    
    return files 
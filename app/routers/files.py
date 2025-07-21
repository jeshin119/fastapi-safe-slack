from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
    return f"https://s3.amazonaws.com/{settings.S3_BUCKET_NAME}/{filename}"

@router.post("/{channel_id}/files", response_model=FileResponse)
async def upload_file(
    channel_id: int,
    file: UploadFile = File(...),
    min_role_id: Optional[int] = Form(None),
    valid_from: Optional[str] = Form(None),
    valid_to: Optional[str] = Form(None),
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
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 파일을 업로드할 권한이 없습니다."
        )
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 크기는 10MB를 초과할 수 없습니다."
        )
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 파일 형식입니다."
        )
    s3_url = upload_to_s3(file, file.filename)
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
    await db.commit()
    await db.refresh(file_record)
    return file_record

@router.get("/{channel_id}/files", response_model=List[FileResponse])
async def get_files(
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
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == current_user.id,
        ChannelMember.channel_id == channel_id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == channel.workspace_id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    result = await db.execute(select(Role).where(Role.id == workspace_membership.role_id))
    user_role = result.scalars().first()
    user_role_level = user_role.level if user_role else 0
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
    files_query = select(FileModel).where(FileModel.channel_id == channel_id)
    if not workspace_membership.is_workspace_admin:
        files_query = files_query.where(
            (FileModel.min_role_id.is_(None)) |
            (FileModel.min_role_id <= user_role_level)
        )
    files_query = files_query.where(
        (FileModel.valid_from.is_(None)) | (FileModel.valid_from <= today)
    ).where(
        (FileModel.valid_to.is_(None)) | (FileModel.valid_to >= today)
    )
    result = await db.execute(files_query)
    files = result.scalars().all()
    return files 
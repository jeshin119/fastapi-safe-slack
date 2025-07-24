from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, File as FileModel, Channel, ChannelMember, WorkspaceMember, Role, Workspace
from app.schemas.file import FileResponse
from app.core.utils import get_current_user, get_current_user_with_context, check_user_permission_by_name
from typing import List, Optional
from datetime import date
import boto3
import os
from app.core.config import settings

router = APIRouter()

def upload_to_s3(file: UploadFile, filename: str) -> str:
    return f"https://s3.amazonaws.com/{settings.S3_BUCKET_NAME}/{filename}"

@router.post("/{channel_name}/files", response_model=FileResponse)
async def upload_file(
    channel_name: str,
    file: UploadFile = File(...),
    min_role_name: Optional[str] = Form(None),
    valid_from: Optional[str] = Form(None),
    valid_to: Optional[str] = Form(None),
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
            detail="채널에 파일을 업로드할 권한이 없습니다."
        )
    
    # 파일 크기 검증
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 크기는 10MB를 초과할 수 없습니다."
        )
    
    # 파일 형식 검증
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
    min_role_id = None
    
    # 날짜 검증
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
    
    # 역할 검증
    if min_role_name:
        result = await db.execute(select(Role).where(Role.name == min_role_name))
        role = result.scalars().first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 직급명입니다."
            )
        min_role_id = role.id
    
    file_record = FileModel(
        uploaded_by=user_context["user_id"],  # 토큰에서 user_id 사용
        channel_id=channel.id,
        filename=file.filename,
        s3_url=s3_url,
        min_role_id=min_role_id,
        valid_from=valid_from_date,
        valid_to=valid_to_date
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)
    
    return {
        "filename": file_record.filename,
        "s3_url": file_record.s3_url,
        "uploaded_by": user_context["user_email"]  # 토큰에서 user_email 사용
    }

@router.get("/{channel_name}/files", response_model=List[FileResponse])
async def get_files(
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
    
    # 워크스페이스 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 역할 정보 조회
    result = await db.execute(select(Role).where(Role.id == workspace_membership.role_id))
    user_role = result.scalars().first()
    user_role_level = user_role.level if user_role else 0
    today = date.today()
    
    # 계약자 기간 확인 (토큰에서 정보 사용)
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
    
    # 파일 조회 쿼리 구성
    files_query = select(FileModel).where(FileModel.channel_id == channel.id)
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
    
    # 사용자 정보를 한 번에 가져오기 (성능 최적화)
    uploader_ids = list(set(file_record.uploaded_by for file_record in files if file_record.uploaded_by))
    uploaders = {}
    if uploader_ids:
        result = await db.execute(select(User).where(User.id.in_(uploader_ids)))
        users = result.scalars().all()
        uploaders = {user.id: user.email for user in users}
    
    return [
        {
            "filename": file_record.filename,
            "s3_url": file_record.s3_url,
            "valid_from": file_record.valid_from,
            "valid_to": file_record.valid_to
        }
        for file_record in files
    ]

@router.get("/{channel_name}/files/{file_id}", response_model=FileResponse)
async def get_file_info(
    channel_name: str,
    file_id: int,
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
    
    # 특정 파일 조회
    result = await db.execute(select(FileModel).where(
        FileModel.id == file_id,
        FileModel.channel_id == channel.id
    ))
    file_record = result.scalars().first()
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # 워크스페이스 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 역할 정보 조회
    result = await db.execute(select(Role).where(Role.id == workspace_membership.role_id))
    user_role = result.scalars().first()
    user_role_level = user_role.level if user_role else 0
    today = date.today()
    
    # 권한 확인
    if not workspace_membership.is_workspace_admin:
        if file_record.min_role_id and file_record.min_role_id > user_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="파일에 접근할 권한이 없습니다."
            )
    
    # 날짜 유효성 확인
    if file_record.valid_from and today < file_record.valid_from:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파일 접근 기간이 시작되지 않았습니다."
        )
    if file_record.valid_to and today > file_record.valid_to:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파일 접근 기간이 종료되었습니다."
        )
    
    # 파일 업로더 정보 조회
    result = await db.execute(select(User).where(User.id == file_record.uploaded_by))
    uploader = result.scalars().first()
    
    return {
        "filename": file_record.filename,
        "s3_url": file_record.s3_url,
        "uploaded_by": uploader.email if uploader else "Unknown",
        "valid_from": file_record.valid_from,
        "valid_to": file_record.valid_to
    }

@router.delete("/{channel_name}/files/{file_id}")
async def delete_file(
    channel_name: str,
    file_id: int,
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
    
    # 특정 파일 조회
    result = await db.execute(select(FileModel).where(
        FileModel.id == file_id,
        FileModel.channel_id == channel.id
    ))
    file_record = result.scalars().first()
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # 파일 업로더 확인 (토큰에서 user_id 사용)
    if file_record.uploaded_by != user_context["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자신이 업로드한 파일만 삭제할 수 있습니다."
        )
    
    # 파일 삭제
    await db.delete(file_record)
    await db.commit()
    
    return {"message": "파일이 삭제되었습니다."} 
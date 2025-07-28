from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, File as FileModel, Role
from app.schemas.file import FileResponse
from app.core.utils import get_current_user_with_context
from app.core.db_utils import get_role_by_name, get_workspace_membership, get_user_role
from app.core.permission_utils import verify_channel_access, verify_file_access, verify_file_owner, verify_contractor_period
from app.core.exception_utils import raise_invalid_date_format
from app.core.date_utils import parse_date, get_current_date
from app.core.file_utils import validate_file_size, validate_file_extension, upload_file_to_s3, download_file_from_s3
from typing import List, Optional

router = APIRouter()




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
    # 워크스페이스와 채널 접근 권한 확인
    workspace, channel = await verify_channel_access(db, user_context["user_id"], workspace_name, channel_name)
    
    # 파일 크기 및 형식 검증
    validate_file_size(file)
    validate_file_extension(file.filename)
    
    s3_url = upload_file_to_s3(file, file.filename)
    
    # 날짜 검증
    valid_from_date = None
    valid_to_date = None
    
    if valid_from:
        try:
            valid_from_date = parse_date(valid_from)
        except HTTPException:
            raise_invalid_date_format()
    
    if valid_to:
        try:
            valid_to_date = parse_date(valid_to)
        except HTTPException:
            raise_invalid_date_format()
    
    # 역할 검증
    min_role_id = None
    if min_role_name:
        role = await get_role_by_name(db, min_role_name)
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
        "file_id": file_record.id,
        "filename": file_record.filename,
        "min_role_name": min_role_name,
        "valid_from": file_record.valid_from,
        "valid_to": file_record.valid_to,
        "uploaded_by": user_context["user_email"],  # 토큰에서 user_email 사용
        "uploaded_at": file_record.uploaded_at
    }

@router.get("/{channel_name}/files", response_model=List[FileResponse])
async def get_files(
    channel_name: str,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 워크스페이스와 채널 접근 권한 확인
    workspace, channel = await verify_channel_access(db, user_context["user_id"], workspace_name, channel_name)
    
    # 워크스페이스 멤버십 정보 조회
    workspace_membership = await get_workspace_membership(db, user_context["user_id"], workspace.id)
    user_role = await get_user_role(db, workspace_membership.role_id)
    user_role_level = user_role.level if user_role else 0
    today = get_current_date()
    
    # 계약자 기간 확인
    await verify_contractor_period(db, user_context["user_id"], workspace.id)
    
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
    
    # 역할 정보를 한 번에 가져오기 (성능 최적화)
    role_ids = list(set(file_record.min_role_id for file_record in files if file_record.min_role_id))
    roles = {}
    if role_ids:
        result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
        role_objects = result.scalars().all()
        roles = {role.id: role.name for role in role_objects}
    
    return [
        {
            "file_id": file_record.id,
            "filename": file_record.filename,
            "min_role_name": roles.get(file_record.min_role_id) if file_record.min_role_id else None,
            "valid_from": file_record.valid_from,
            "valid_to": file_record.valid_to,
            "uploaded_by": uploaders.get(file_record.uploaded_by, "Unknown"),
            "uploaded_at": file_record.uploaded_at
        }
        for file_record in files
    ]

@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 파일 접근 권한 확인 (파일 ID만으로 조회)
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalars().first()
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # S3에서 파일 스트림 다운로드
    return download_file_from_s3(file_record.filename) 

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    
    # 파일 소유자 확인 및 파일 조회
    file_record = await verify_file_owner(db, user_context["user_id"], file_id)
    
    # 파일 삭제
    await db.delete(file_record)
    await db.commit()
    
    return {"message": "파일이 삭제되었습니다."} 

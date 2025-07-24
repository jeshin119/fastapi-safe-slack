from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, File as FileModel, Channel, ChannelMember, WorkspaceMember, Role, Workspace
from app.schemas.file import FileResponse
from app.core.utils import get_current_user, get_current_user_with_context
from typing import List, Optional
from datetime import date
import boto3
import os
from app.core.config import settings
from fastapi.responses import RedirectResponse
import uuid

router = APIRouter()

def upload_to_s3(file: UploadFile, filename: str) -> str:
    """실제 S3에 파일을 업로드하고 URL을 반환"""
    try:
        # S3 클라이언트 생성
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # 고유한 파일명 생성 (UUID 사용)
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # 파일 내용 읽기
        file_content = file.file.read()
        
        # S3에 업로드
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type,
            ACL='public-read'
        )
        
        # 파일 포인터를 다시 처음으로 되돌림 (다른 곳에서 사용할 수 있도록)
        file.file.seek(0)
        
        # S3 URL 반환
        return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 업로드 중 오류가 발생했습니다: {str(e)}"
        )

def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """S3 pre-signed URL 생성"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # S3 URL에서 키 추출
        if s3_key.startswith('http'):
            # URL에서 키 부분만 추출
            s3_key = s3_key.split(f"{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/")[-1]
        
        # pre-signed URL 생성
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        
        return presigned_url
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pre-signed URL 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/{channel_name}/files")
async def upload_file(
    channel_name: str,
    file: UploadFile = File(...),
    min_role_name: Optional[str] = Form(None),
    valid_from: Optional[str] = Form(None),
    valid_to: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):

    
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
    
    # 워크스페이스 멤버십 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 채널 멤버십 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
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
        uploaded_by=user_context["user_id"],
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
        "message": "파일이 업로드되었습니다."
    }

@router.get("/{channel_name}/files")
async def get_files(
    channel_name: str,
    workspace_name: str = Query(..., description="워크스페이스 이름"),
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
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
    
    # 채널 멤버십 확인 (채널에 가입된 유저만 파일 조회 가능)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 가입되어 있지 않아 파일을 조회할 수 없습니다."
        )
    
    # 모든 파일 조회 (권한 검증은 다운로드 시에만)
    files_query = select(FileModel).where(FileModel.channel_id == channel.id)
    result = await db.execute(files_query)
    files = result.scalars().all()
    
    # 사용자 정보를 한 번에 가져오기 (성능 최적화)
    uploader_ids = list(set(file_record.uploaded_by for file_record in files if file_record.uploaded_by))
    uploaders = {}
    if uploader_ids:
        result = await db.execute(select(User).where(User.id.in_(uploader_ids)))
        users = result.scalars().all()
        uploaders = {user.id: user.name for user in users}
    
    # 역할 정보 가져오기
    role_ids = list(set(file_record.min_role_id for file_record in files if file_record.min_role_id))
    roles = {}
    if role_ids:
        result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
        role_list = result.scalars().all()
        roles = {role.id: role.name for role in role_list}
    
    # 파일 크기와 MIME 타입 계산
    file_list = []
    for file_record in files:
        try:
            # S3에서 파일 정보 가져오기
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            # S3 URL에서 키 추출
            s3_key = file_record.s3_url.split(f"{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/")[-1]
            
            # S3에서 파일 정보 조회
            response = s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
            file_size = response.get('ContentLength', 0)
            mime_type = response.get('ContentType', 'application/octet-stream')
            
        except Exception:
            # S3 조회 실패 시 기본값 사용
            file_size = 0
            mime_type = 'application/octet-stream'
        
        file_list.append({
            "file_id": file_record.id,
            "filename": file_record.filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "description": "",  # files 테이블에 description 필드가 없으므로 빈 문자열
            "min_role_name": roles.get(file_record.min_role_id, ""),
            "valid_from": file_record.valid_from,
            "valid_to": file_record.valid_to,
            "uploaded_by": uploaders.get(file_record.uploaded_by, "Unknown"),
            "uploaded_at": file_record.uploaded_at,
            "download_url": f"/files/{file_record.id}/download"
        })
    
    return file_list

@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 파일 정보 조회
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalars().first()
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # 채널 정보 조회
    result = await db.execute(select(Channel).where(Channel.id == file_record.channel_id))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 워크스페이스 정보 조회
    result = await db.execute(select(Workspace).where(Workspace.id == channel.workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 워크스페이스 멤버십 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 채널 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 역할 기반 권한 확인
    if file_record.min_role_id:
        result = await db.execute(select(Role).where(Role.id == workspace_membership.role_id))
        user_role = result.scalars().first()
        user_role_level = user_role.level if user_role else 0
        
        result = await db.execute(select(Role).where(Role.id == file_record.min_role_id))
        required_role = result.scalars().first()
        required_role_level = required_role.level if required_role else 0
        
        if user_role_level < required_role_level and not workspace_membership.is_workspace_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="파일에 접근할 권한이 없습니다."
            )
    
    # 날짜 기반 권한 확인
    today = date.today()
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
    
    # S3 pre-signed URL 생성
    presigned_url = generate_presigned_url(file_record.s3_url)
    return RedirectResponse(url=presigned_url)

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 파일 정보 조회
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalars().first()
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # 채널 정보 조회
    result = await db.execute(select(Channel).where(Channel.id == file_record.channel_id))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 워크스페이스 정보 조회
    result = await db.execute(select(Workspace).where(Workspace.id == channel.workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 워크스페이스 멤버십 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 채널 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 파일 업로더 또는 채널 관리자 확인
    is_uploader = file_record.uploaded_by == user_context["user_id"]
    is_channel_admin = channel.created_by == user_context["user_id"]
    
    if not is_uploader and not is_channel_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파일을 삭제할 권한이 없습니다."
        )
    
    # S3에서 파일 삭제
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # S3 URL에서 키 추출
        s3_key = file_record.s3_url.split(f"{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/")[-1]
        
        # S3에서 파일 삭제
        s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        
    except Exception as e:
        # S3 삭제 실패 시에도 DB는 삭제 (일관성 유지)
        print(f"S3 파일 삭제 실패: {str(e)}")
    
    # DB에서 파일 정보 삭제
    await db.delete(file_record)
    await db.commit()
    
    return {"message": "파일이 삭제되었습니다."} 
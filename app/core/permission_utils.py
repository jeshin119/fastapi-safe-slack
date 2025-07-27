from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import Workspace, Channel, WorkspaceMember, ChannelMember, File as FileModel, User, Role
from app.core.db_utils import get_workspace_by_name, get_channel_by_name, get_workspace_membership, get_channel_membership, get_user_role
from app.core.date_utils import get_current_date
from fastapi import HTTPException, status
from typing import Tuple, Optional, Dict
from datetime import date


async def verify_workspace_access(db: AsyncSession, user_id: int, workspace_name: str) -> Workspace:
    """
    사용자의 워크스페이스 접근 권한을 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        workspace_name: 워크스페이스 이름
        
    Returns:
        Workspace: 워크스페이스 객체
        
    Raises:
        HTTPException: 워크스페이스를 찾을 수 없거나 접근 권한이 없는 경우
    """
    workspace = await get_workspace_by_name(db, workspace_name)
    membership = await get_workspace_membership(db, user_id, workspace.id)
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    return workspace


async def verify_channel_access(db: AsyncSession, user_id: int, workspace_name: str, channel_name: str) -> Tuple[Workspace, Channel]:
    """
    사용자의 채널 접근 권한을 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        workspace_name: 워크스페이스 이름
        channel_name: 채널 이름
        
    Returns:
        Tuple[Workspace, Channel]: 워크스페이스와 채널 객체
        
    Raises:
        HTTPException: 워크스페이스나 채널을 찾을 수 없거나 접근 권한이 없는 경우
    """
    workspace = await verify_workspace_access(db, user_id, workspace_name)
    channel = await get_channel_by_name(db, channel_name, workspace.id)
    
    membership = await get_channel_membership(db, user_id, channel.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    return workspace, channel


async def verify_workspace_admin(db: AsyncSession, user_id: int, workspace_id: int) -> bool:
    """
    사용자가 워크스페이스 관리자인지 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        workspace_id: 워크스페이스 ID
        
    Returns:
        bool: 관리자인 경우 True
        
    Raises:
        HTTPException: 관리자가 아닌 경우
    """
    membership = await get_workspace_membership(db, user_id, workspace_id)
    
    if not membership or not membership.is_workspace_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자 권한이 필요합니다."
        )
    
    return True


async def verify_channel_creator(db: AsyncSession, user_id: int, channel_id: int) -> bool:
    """
    사용자가 채널 생성자인지 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        channel_id: 채널 ID
        
    Returns:
        bool: 생성자인 경우 True
        
    Raises:
        HTTPException: 생성자가 아닌 경우
    """
    from app.models.models import Channel
    from sqlalchemy import select
    
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalars().first()
    
    if not channel or channel.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널 생성자만 이 작업을 수행할 수 있습니다."
        )
    
    return True


async def check_user_permission(user: User, workspace_id: int, db: AsyncSession, required_role_level: int = 1) -> bool:
    """
    사용자의 워크스페이스 권한을 확인합니다.
    
    Args:
        user: 사용자 객체
        workspace_id: 워크스페이스 ID
        db: 데이터베이스 세션
        required_role_level: 필요한 역할 레벨 (기본값: 1)
        
    Returns:
        bool: 권한이 있는 경우 True
    """
    # 워크스페이스 멤버십 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    membership = result.scalars().first()
    
    if not membership:
        return False
    
    # 관리자인 경우 모든 권한 허용
    if membership.is_workspace_admin:
        return True
    
    # 역할 레벨 확인
    result = await db.execute(select(Role).where(Role.id == membership.role_id))
    role = result.scalars().first()
    
    if not role:
        return False
    
    if role.level < required_role_level:
        return False
    
    # 계약자 기간 확인
    if membership.is_contractor:
        today = get_current_date()
        if membership.start_date and today < membership.start_date:
            return False
        if membership.end_date and today > membership.end_date:
            return False
    
    return True


async def check_user_permission_by_name(
    user_context: dict, 
    workspace_name: str, 
    required_role_name: str = None,
    require_admin: bool = False
) -> bool:
    """
    토큰의 context 정보를 사용해서 권한을 확인하는 함수
    DB 조회 없이 토큰에서 바로 확인
    """
    # 워크스페이스 확인
    if user_context.get("workspace_name") != workspace_name:
        return False
    
    # 관리자 권한 확인
    if require_admin and not user_context.get("is_workspace_admin", False):
        return False
    
    # 역할 권한 확인
    if required_role_name:
        user_role_name = user_context.get("role_name")
        if not user_role_name:
            return False
        
        # 역할 레벨 비교 (간단한 구현)
        role_levels = {
            "사원": 1, "대리": 2, "과장": 3, 
            "부장": 4, "이사": 5, "대표": 6
        }
        
        user_level = role_levels.get(user_role_name, 0)
        required_level = role_levels.get(required_role_name, 0)
        
        if user_level < required_level:
            return False
    
    # 계약자 기간 확인
    if user_context.get("is_contractor", False):
        today = get_current_date()
        start_date = user_context.get("start_date")
        end_date = user_context.get("end_date")
        
        if start_date:
            start_date = datetime.fromisoformat(start_date).date()
            if today < start_date:
                return False
        
        if end_date:
            end_date = datetime.fromisoformat(end_date).date()
            if today > end_date:
                return False
    
    return True


async def get_user_workspace_info(user: User, workspace_id: int, db: AsyncSession) -> Optional[Dict]:
    """
    사용자의 워크스페이스 정보를 조회합니다.
    """
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    membership = result.scalars().first()
    
    if not membership:
        return None
    
    result = await db.execute(select(Role).where(Role.id == membership.role_id))
    role = result.scalars().first()
    
    return {
        "user_id": user.id,
        "workspace_id": workspace_id,
        "role_id": membership.role_id,
        "role_level": role.level if role else 0,
        "is_workspace_admin": membership.is_workspace_admin,
        "is_contractor": membership.is_contractor,
        "start_date": membership.start_date,
        "end_date": membership.end_date
    }


async def verify_file_access(db: AsyncSession, user_id: int, file_id: int, workspace_name: str, channel_name: str) -> FileModel:
    """
    사용자의 파일 접근 권한을 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        file_id: 파일 ID
        workspace_name: 워크스페이스 이름
        channel_name: 채널 이름
        
    Returns:
        FileModel: 파일 객체
        
    Raises:
        HTTPException: 파일을 찾을 수 없거나 접근 권한이 없는 경우
    """
    from sqlalchemy import select
    from datetime import date
    
    # 워크스페이스와 채널 접근 권한 확인
    workspace, channel = await verify_channel_access(db, user_id, workspace_name, channel_name)
    
    # 파일 조회
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
    
    # 워크스페이스 멤버십 정보 조회
    workspace_membership = await get_workspace_membership(db, user_id, workspace.id)
    user_role = await get_user_role(db, workspace_membership.role_id)
    user_role_level = user_role.level if user_role else 0
    today = date.today()
    
    # 관리자가 아닌 경우 역할 기반 권한 확인
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
    
    return file_record


async def verify_contractor_period(db: AsyncSession, user_id: int, workspace_id: int) -> bool:
    """
    계약자의 계약 기간을 확인합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        workspace_id: 워크스페이스 ID
        
    Returns:
        bool: 계약 기간이 유효한 경우 True
        
    Raises:
        HTTPException: 계약 기간이 유효하지 않은 경우
    """
    from datetime import date
    
    membership = await get_workspace_membership(db, user_id, workspace_id)
    
    if membership and membership.is_contractor:
        today = date.today()
        
        if membership.start_date and today < membership.start_date:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="계약 기간이 시작되지 않았습니다."
            )
        
        if membership.end_date and today > membership.end_date:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="계약 기간이 종료되었습니다."
            )
    
    return True


async def verify_file_owner(db: AsyncSession, user_id: int, file_id: int) -> FileModel:
    """
    사용자가 파일의 소유자인지 확인하고 파일 객체를 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        file_id: 파일 ID
        
    Returns:
        FileModel: 파일 객체
        
    Raises:
        HTTPException: 파일을 찾을 수 없거나 소유자가 아닌 경우
    """
    from sqlalchemy import select
    from app.models.models import File as FileModel
    
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalars().first()
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    if file_record.uploaded_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자신이 업로드한 파일만 삭제할 수 있습니다."
        )
    
    return file_record 
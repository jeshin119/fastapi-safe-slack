from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User, Role
import secrets
import string
from sqlalchemy import select


# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 토큰 보안
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_user_with_context(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    토큰에서 사용자 정보를 가져오는 함수
    간소화된 토큰 구조에 맞춤
    """
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": payload.get("user_id"),
        "user_email": payload.get("user_email"),
        "user_name": payload.get("user_name")
    }

def generate_invite_code(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)

async def check_user_permission(user: User, workspace_id: int, db: AsyncSession, required_role_level: int = 1) -> bool:
    from app.models.models import WorkspaceMember, Role
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.workspace_id == workspace_id
    ))
    membership = result.scalars().first()
    if not membership:
        return False
    if membership.is_workspace_admin:
        return True
    result = await db.execute(select(Role).where(Role.id == membership.role_id))
    role = result.scalars().first()
    if not role or role.level < required_role_level:
        return False
    if membership.is_contractor:
        today = datetime.now().date()
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
        today = datetime.now().date()
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

async def get_user_workspace_info(user: User, workspace_id: int, db: AsyncSession) -> Optional[dict]:
    from app.models.models import WorkspaceMember, Role
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
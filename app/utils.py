from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, Role
import secrets
import string

# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 토큰 보안
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """JWT 토큰 검증"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """현재 인증된 사용자 가져오기"""
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
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

def generate_invite_code(length: int = 8) -> str:
    """초대 코드 생성"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_verification_token() -> str:
    """이메일 인증 토큰 생성"""
    return secrets.token_urlsafe(32)

def check_user_permission(user: User, workspace_id: int, required_role_level: int = 1) -> bool:
    """사용자 권한 확인"""
    from app.models import WorkspaceMember, Role
    
    # 사용자의 워크스페이스 멤버십 확인
    membership = user.workspace_members.filter(
        WorkspaceMember.workspace_id == workspace_id
    ).first()
    
    if not membership:
        return False
    
    # 관리자인 경우 모든 권한 허용
    if membership.is_workspace_admin:
        return True
    
    # 직급 레벨 확인
    role = db.query(Role).filter(Role.id == membership.role_id).first()
    if not role or role.level < required_role_level:
        return False
    
    # 계약직인 경우 기간 확인
    if membership.is_contractor:
        today = datetime.now().date()
        if membership.start_date and today < membership.start_date:
            return False
        if membership.end_date and today > membership.end_date:
            return False
    
    return True

def get_user_workspace_info(user: User, workspace_id: int) -> Optional[dict]:
    """사용자의 워크스페이스 정보 가져오기"""
    from app.models import WorkspaceMember, Role
    
    membership = user.workspace_members.filter(
        WorkspaceMember.workspace_id == workspace_id
    ).first()
    
    if not membership:
        return None
    
    role = db.query(Role).filter(Role.id == membership.role_id).first()
    
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
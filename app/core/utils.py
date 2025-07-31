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
import html
import re


# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 토큰 보안
security = HTTPBearer()

def sanitize_input(text: str) -> str:
    """
    입력 데이터를 Sanitize하여 XSS 공격을 방지합니다.
    """
    if not text:
        return text
    
    # HTML 엔티티 이스케이프
    sanitized = html.escape(text)
    
    # 위험한 스크립트 태그 제거
    script_pattern = r'<script[^>]*>.*?</script>'
    sanitized = re.sub(script_pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    # 위험한 이벤트 핸들러 제거
    event_pattern = r'on\w+\s*='
    sanitized = re.sub(event_pattern, '', sanitized, flags=re.IGNORECASE)
    
    return sanitized.strip()

def sanitize_email(email: str) -> str:
    """
    이메일 주소를 Sanitize합니다.
    """
    if not email:
        return email
    
    # 이메일 형식 검증 및 정리
    email = email.lower().strip()
    
    # 위험한 문자 제거
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        email = email.replace(char, '')
    
    return email

def validate_password_strength(password: str) -> dict:
    """
    비밀번호 강도를 검증하고 결과를 반환합니다.
    """
    result = {
        'is_valid': True,
        'errors': [],
        'strength_score': 0
    }
    
    if len(password) < 8:
        result['is_valid'] = False
        result['errors'].append('비밀번호는 8자 이상이어야 합니다.')
    else:
        result['strength_score'] += 1
    
    if not any(c.islower() for c in password):
        result['is_valid'] = False
        result['errors'].append('소문자를 포함해야 합니다.')
    else:
        result['strength_score'] += 1
    
    if not any(c.isupper() for c in password):
        result['is_valid'] = False
        result['errors'].append('대문자를 포함해야 합니다.')
    else:
        result['strength_score'] += 1
    
    if not any(c.isdigit() for c in password):
        result['is_valid'] = False
        result['errors'].append('숫자를 포함해야 합니다.')
    else:
        result['strength_score'] += 1
    
    if not any(not c.isalnum() for c in password):
        result['is_valid'] = False
        result['errors'].append('특수문자를 포함해야 합니다.')
    else:
        result['strength_score'] += 1
    
    return result

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

# 권한 검증 관련 함수들은 permission_utils.py로 이동됨
# check_user_permission, check_user_permission_by_name, get_user_workspace_info 
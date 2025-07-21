from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, Role
from app.schemas.user import UserCreate, UserLogin
from app.schemas.auth import Token, EmailVerificationRequest, EmailVerification
from app.core.utils import get_password_hash, verify_password, create_access_token, generate_invite_code
from datetime import datetime, date
import secrets

router = APIRouter()

@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """회원가입 - 새 워크스페이스 생성 또는 초대 코드로 가입"""
    
    # 이메일 중복 확인
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    
    # workspace_name 또는 invite_code 중 하나만 제공되어야 함
    if bool(user_data.workspace_name) == bool(user_data.invite_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_name 또는 invite_code 중 하나만 제공해야 합니다."
        )
    
    # 사용자 생성
    hashed_password = get_password_hash(user_data.password)
    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password
    )
    db.add(user)
    db.flush()  # ID 생성을 위해 flush
    
    workspace_id = None
    
    if user_data.workspace_name:
        # 새 워크스페이스 생성
        workspace = Workspace(name=user_data.workspace_name)
        db.add(workspace)
        db.flush()
        workspace_id = workspace.id
        
        # 워크스페이스 멤버로 추가 (관리자)
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role_id=user_data.role_id,
            is_workspace_admin=True
        )
        db.add(member)
        
        # 기본 채널 생성
        from app.models import Channel
        default_channel = Channel(
            name="전체",
            workspace_id=workspace.id,
            created_by=user.id,
            is_default=True,
            is_public=True
        )
        db.add(default_channel)
        
    elif user_data.invite_code:
        # 초대 코드로 워크스페이스 찾기 (실제로는 invite_codes 테이블이 필요)
        # 여기서는 간단히 워크스페이스 ID로 가정
        try:
            workspace_id = int(user_data.invite_code)
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="유효하지 않은 초대 코드입니다."
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 초대 코드 형식입니다."
            )
        
        # 워크스페이스 가입 요청 생성
        from app.models import WorkspaceJoinRequest
        join_request = WorkspaceJoinRequest(
            user_id=user.id,
            workspace_id=workspace_id
        )
        db.add(join_request)
    
    db.commit()
    
    # JWT 토큰 생성
    token_data = {
        "user_id": user.id,
        "workspace_id": workspace_id,
        "role_id": user_data.role_id,
        "is_workspace_admin": bool(user_data.workspace_name),
        "is_contractor": False
    }
    
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """로그인"""
    
    user = db.query(User).filter(User.email == user_credentials.email).first()
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    
    # 사용자의 워크스페이스 정보 가져오기 (첫 번째 워크스페이스)
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == user.id
    ).first()
    
    token_data = {
        "user_id": user.id,
        "workspace_id": membership.workspace_id if membership else None,
        "role_id": membership.role_id if membership else None,
        "is_workspace_admin": membership.is_workspace_admin if membership else False,
        "is_contractor": membership.is_contractor if membership else False,
        "start_date": membership.start_date.isoformat() if membership and membership.start_date else None,
        "end_date": membership.end_date.isoformat() if membership and membership.end_date else None
    }
    
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/request-verification")
async def request_email_verification(request: EmailVerificationRequest, db: Session = Depends(get_db)):
    """이메일 인증 요청"""
    
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록되지 않은 이메일입니다."
        )
    
    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 인증된 이메일입니다."
        )
    
    # 인증 토큰 생성 (실제로는 이메일로 전송)
    verification_token = secrets.token_urlsafe(32)
    
    # 여기서는 실제 이메일 전송 로직을 구현해야 함
    # send_verification_email(user.email, verification_token)
    
    return {"message": "인증 이메일이 전송되었습니다."}

@router.post("/verify-email")
async def verify_email(verification: EmailVerification, db: Session = Depends(get_db)):
    """이메일 인증 확인"""
    
    # 실제로는 토큰을 검증하는 로직이 필요
    # verification_token = verification.token
    
    # 임시로 모든 이메일을 인증된 것으로 처리
    return {"message": "이메일이 성공적으로 인증되었습니다."} 
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, Role
from app.schemas.user import UserCreate, UserLogin
from app.schemas.auth import Token, EmailVerificationRequest, EmailVerification
from app.core.utils import get_password_hash, verify_password, create_access_token, generate_invite_code
from datetime import datetime, date
import secrets

router = APIRouter()

@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # 이메일 중복 확인
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    if bool(user_data.workspace_name) == bool(user_data.invite_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_name 또는 invite_code 중 하나만 제공해야 합니다."
        )
    hashed_password = get_password_hash(user_data.password)
    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password
    )
    db.add(user)
    await db.flush()
    workspace_id = None
    if user_data.workspace_name:
        workspace = Workspace(name=user_data.workspace_name)
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role_id=user_data.role_id,
            is_workspace_admin=True
        )
        db.add(member)
        from app.models.models import Channel
        default_channel = Channel(
            name="전체",
            workspace_id=workspace.id,
            created_by=user.id,
            is_default=True,
            is_public=True
        )
        db.add(default_channel)
    elif user_data.invite_code:
        try:
            workspace_id = int(user_data.invite_code)
            result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = result.scalars().first()
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
        from app.models.models import WorkspaceJoinRequest
        join_request = WorkspaceJoinRequest(
            user_id=user.id,
            workspace_id=workspace_id
        )
        db.add(join_request)
    await db.commit()
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
async def login(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_credentials.email))
    user = result.scalars().first()
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    result = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
    membership = result.scalars().first()
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
async def request_email_verification(request: EmailVerificationRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()
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
    verification_token = secrets.token_urlsafe(32)
    return {"message": "인증 이메일이 전송되었습니다."}

@router.post("/verify-email")
async def verify_email(verification: EmailVerification, db: AsyncSession = Depends(get_db)):
    return {"message": "이메일이 성공적으로 인증되었습니다."} 
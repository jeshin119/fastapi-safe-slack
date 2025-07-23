from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, Role
from app.schemas.user import UserCreate, UserLogin
from app.schemas.auth import Token, EmailVerificationRequest, EmailVerification
from app.models.invite_code import InviteCode
from app.schemas.invite_code import InviteCodeCreate, InviteCodeResponse
from app.core.utils import get_current_user, get_password_hash, verify_password, create_access_token, generate_invite_code
from datetime import datetime, date
import secrets

router = APIRouter()

@router.post("/signup")
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
    
    # role_name으로 role_id 찾기
    result = await db.execute(select(Role).where(Role.name == user_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
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
        # 워크스페이스 이름 중복 확인
        result = await db.execute(select(Workspace).where(Workspace.name == user_data.workspace_name))
        existing_ws = result.scalars().first()
        if existing_ws:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 워크스페이스 이름입니다."
            )
        workspace = Workspace(name=user_data.workspace_name)
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role_id=role.id,
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
        # 초대코드 테이블에서 code로 조회 및 검증
        result = await db.execute(
            select(InviteCode).where(InviteCode.code == user_data.invite_code)
        )
        invite = result.scalars().first()
        if (
            not invite
            or invite.used
            or (invite.expires_at and invite.expires_at < datetime.utcnow())
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 초대 코드입니다."
            )
        workspace_id = invite.workspace_id
        # 1회용 코드라면 사용 처리
        invite.used = True
        invite.used_at = datetime.utcnow()
        await db.commit()
        # 워크스페이스 멤버로 바로 추가 (A안)
        is_contractor = bool(invite.expires_at)
        end_date = invite.expires_at if invite.expires_at else None
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace_id,
            role_id=role.id,
            is_workspace_admin=False,
            is_contractor=is_contractor,
            end_date=end_date
        )
        db.add(member)
        await db.commit()
    await db.commit()
    return {"message": f"{user_data.name}님, 회원가입을 축하합니다!"}


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_credentials.email))
    user = result.scalars().first()
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    
    # 워크스페이스 멤버십 정보 조회
    result = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
    membership = result.scalars().first()
    
    if membership:
        # 워크스페이스 정보 조회
        result = await db.execute(select(Workspace).where(Workspace.id == membership.workspace_id))
        workspace = result.scalars().first()
        
        # 역할 정보 조회
        result = await db.execute(select(Role).where(Role.id == membership.role_id))
        role = result.scalars().first()
        
        token_data = {
            "user_id": user.id,
            "user_email": user.email,
            "workspace_id": membership.workspace_id,
            "workspace_name": workspace.name if workspace else None,
            "role_id": membership.role_id,
            "role_name": role.name if role else None,
            "is_workspace_admin": membership.is_workspace_admin,
            "is_contractor": membership.is_contractor,
            "start_date": membership.start_date.isoformat() if membership.start_date else None,
            "end_date": membership.end_date.isoformat() if membership.end_date else None
        }
    else:
        token_data = {
            "user_id": user.id,
            "user_email": user.email,
            "workspace_id": None,
            "workspace_name": None,
            "role_id": None,
            "role_name": None,
            "is_workspace_admin": False,
            "is_contractor": False,
            "start_date": None,
            "end_date": None
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

@router.post("/invite-codes", response_model=InviteCodeResponse)
async def create_invite_code(
    invite_data: InviteCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)  # 워크스페이스 관리자 인증 필요
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == invite_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 워크스페이스 관리자인지 검증
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 초대 코드를 생성할 수 있습니다."
        )
    
    code = generate_invite_code()
    invite = InviteCode(
        code=code,
        workspace_id=workspace.id,
        expires_at=invite_data.expires_at,
        created_by=current_user.id
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    
    # 응답에 workspace_name 포함
    return {
        "code": invite.code,
        "workspace_name": workspace.name,
        "expires_at": invite.expires_at,
        "used": invite.used,
        "created_at": invite.created_at
    }
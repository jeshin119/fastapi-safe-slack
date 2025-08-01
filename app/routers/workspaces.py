from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Workspace, WorkspaceMember, WorkspaceJoinRequest, Channel, Role, InviteCode, ChannelMember
from app.schemas.workspace import WorkspaceJoinRequestCreate, WorkspaceApproveRequest, WorkspaceCreateRequest, WorkspaceCreateResponse, WorkspaceRejectRequest
from app.schemas.channel import ChannelResponse
from app.core.utils import get_current_user_with_context
from app.core.business_utils import create_workspace_with_admin, get_workspace_join_requests_for_admin, get_user_workspaces_with_member_count
from datetime import datetime, date
from typing import List
from app.models.workspace import RequestStatus
from pydantic import BaseModel


router = APIRouter()

class WorkspaceRequest(BaseModel):
    workspace_name: str

class WorkspaceJoinRequestList(BaseModel):
    request_id: int
    user_email: str
    user_name: str
    role_name: str
    is_contractor: bool = False
    requested_at: datetime

class WorkspaceMemberList(BaseModel):
    user_id: int
    name: str
    email: str
    role_name: str

class WorkspaceOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class WorkspaceSelectRequest(BaseModel):
    workspace_name: str

class WorkspaceSelectResponse(BaseModel):
    workspace_name: str
    is_workspace_admin: bool
    message: str

class WorkspaceKickRequest(BaseModel):
    workspace_name: str
    user_id: int  # 추방 대상


@router.post("/create")
async def create_workspace(
    request_data: WorkspaceCreateRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    result = await create_workspace_with_admin(db, request_data.workspace_name, user_context["user_id"])
    return WorkspaceCreateResponse(**result)

@router.post("/join-request")
async def request_workspace_join(
    request_data: WorkspaceJoinRequestCreate,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 초대 코드로 워크스페이스 찾기
    result = await db.execute(select(InviteCode).where(InviteCode.code == request_data.invite_code))
    invite_code = result.scalars().first()
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 초대 코드입니다."
        )
    
    # 초대 코드 만료 확인
    if invite_code.expires_at and invite_code.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="만료된 초대 코드입니다."
        )
    
    # 초대 코드 사용 여부 확인
    if invite_code.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용된 초대 코드입니다."
        )
    
    # 이미 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == invite_code.workspace_id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )
    
    # role_name으로 role_id 찾기
    result = await db.execute(select(Role).where(Role.name == request_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )
    
    # 기존 요청 확인
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.user_id == user_context["user_id"],
        WorkspaceJoinRequest.invite_code_id == invite_code.id,
        WorkspaceJoinRequest.status == "pending"
    ))
    existing_request = result.scalars().first()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 참여 요청이 대기 중입니다."
        )
    
    join_request = WorkspaceJoinRequest(
        user_id=user_context["user_id"],
        invite_code_id=invite_code.id,
        role_id=role.id
    )
    db.add(join_request)
    
    # 초대 코드를 사용됨으로 표시
    invite_code.used = True
    invite_code.used_at = datetime.utcnow()
    
    await db.commit()
    return {
        "message": "워크스페이스 가입 요청이 전송되었습니다."
    }

@router.post("/join-requests-list")
async def get_workspace_join_requests(
    workspace_data: WorkspaceCreateRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    return await get_workspace_join_requests_for_admin(db, workspace_data.workspace_name, user_context["user_id"])


@router.post("/approve")
async def approve_workspace_join(
    approve_data: WorkspaceApproveRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 가입 요청 찾기 (request_id)
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.id == approve_data.request_id,
        WorkspaceJoinRequest.status == "pending"
    ))
    join_request = result.scalars().first()
    if not join_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 가입 요청을 찾을 수 없습니다."
        )

    # 요청한 사용자 정보 확인
    result = await db.execute(select(User).where(User.id == join_request.user_id))
    request_user = result.scalars().first()
    if not request_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요청한 사용자를 찾을 수 없습니다."
        )

    # user_name 검증
    if request_user.name != approve_data.user_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="요청한 사용자 이름이 일치하지 않습니다."
        )

    # 초대 코드를 통해 워크스페이스 정보 얻기
    result = await db.execute(select(InviteCode).where(InviteCode.id == join_request.invite_code_id))
    invite_code = result.scalars().first()
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대 코드를 찾을 수 없습니다."
        )

    # 워크스페이스 관리자 권한 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == invite_code.workspace_id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스 관리자만 승인할 수 있습니다."
        )

    # 역할 찾기 (승인 시 설정할 역할)
    result = await db.execute(select(Role).where(Role.name == approve_data.role_name))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 직급명입니다."
        )

    # 이미 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == join_request.user_id,
        WorkspaceMember.workspace_id == invite_code.workspace_id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 워크스페이스 멤버입니다."
        )

    # 멤버로 추가
    member = WorkspaceMember(
        user_id=join_request.user_id,
        workspace_id=invite_code.workspace_id,
        role_id=role.id,
        is_workspace_admin=False,
        is_contractor=approve_data.is_contractor,
        end_date=approve_data.expires_at
    )
    db.add(member)

    # 요청 상태를 승인으로 변경
    join_request.status = "approved"
    join_request.processed_at = datetime.utcnow()
    join_request.role_name = approve_data.role_name  # ✅ 관리자 승인값으로 덮어쓰기
    join_request.role_id = role.id
    db.add(join_request)

    # 초대 코드를 사용됨으로 표시
    invite_code.used = True
    invite_code.used_at = datetime.utcnow()

    # ✅ 기본 채널에 자동 참여 처리
    default_channel_result = await db.execute(select(Channel).where(
        Channel.workspace_id == invite_code.workspace_id,
        Channel.is_default == True
    ))
    default_channel = default_channel_result.scalars().first()

    if default_channel:
        db.add(ChannelMember(
            channel_id=default_channel.id,
            user_id=join_request.user_id
        ))

    await db.commit()
    return {"message": "사용자가 워크스페이스에 추가되었습니다."}


@router.post("/members")
async def get_workspace_members(
    workspace_data: WorkspaceRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 현재 사용자가 워크스페이스 멤버인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # 워크스페이스 멤버 정보 조회 (JOIN으로 한 번에 가져오기)
    result = await db.execute(
        select(WorkspaceMember, User, Role)
        .join(User, WorkspaceMember.user_id == User.id)
        .join(Role, WorkspaceMember.role_id == Role.id)
        .where(WorkspaceMember.workspace_id == workspace.id)
    )
    members_data = result.all()
    
    return [
        {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "role_name": role.name
        }
        for member, user, role in members_data
    ] 

@router.get("/workspaces_list", response_model=List[dict])
async def get_my_workspace_names_with_roles(
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    return await get_user_workspaces_with_member_count(db, user_context["user_id"])

@router.post("/workspaces_select", response_model=WorkspaceSelectResponse)
async def select_workspace(
    request: WorkspaceSelectRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    user_id = user_context["user_id"]

    result = await db.execute(
        select(
            Workspace.name,
            WorkspaceMember.is_workspace_admin,
            WorkspaceMember.is_contractor,
            WorkspaceMember.end_date
        )
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            Workspace.name == request.workspace_name,
            WorkspaceMember.user_id == user_id
        )
    )

    data = result.first()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 워크스페이스에 접근할 수 없습니다."
        )

    name, is_admin, is_contractor, end_date = data

    # ✅ 파견자 + 만료일 검사
    if is_contractor and end_date and end_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"해당 워크스페이스의 파견 기간이 {end_date.strftime('%Y-%m-%d')}에 만료되어 입장할 수 없습니다."
        )

    return {
        "workspace_name": name,
        "is_workspace_admin": is_admin,
        "message": f'"{name}" 워크스페이스에 입장했습니다.'
    }

@router.post("/reject")
async def reject_workspace_join(
    reject_data: WorkspaceRejectRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 가입 요청 찾기
    result = await db.execute(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.id == reject_data.request_id,
        WorkspaceJoinRequest.status == "pending"
    ))
    join_request = result.scalars().first()
    if not join_request:
        raise HTTPException(status_code=404, detail="대기 중인 가입 요청이 없습니다.")

    # 요청한 사용자 정보 확인
    result = await db.execute(select(User).where(User.id == join_request.user_id))
    request_user = result.scalars().first()
    if not request_user or request_user.name != reject_data.user_name:
        raise HTTPException(status_code=400, detail="요청 사용자 정보가 일치하지 않습니다.")

    # 초대 코드 조회 → 워크스페이스 확인
    result = await db.execute(select(InviteCode).where(InviteCode.id == join_request.invite_code_id))
    invite_code = result.scalars().first()
    if not invite_code:
        raise HTTPException(status_code=404, detail="초대 코드가 유효하지 않습니다.")

    # 현재 유저가 워크스페이스 관리자 권한인지 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == invite_code.workspace_id,
        WorkspaceMember.is_workspace_admin == True
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(status_code=403, detail="관리자만 거부할 수 있습니다.")

    # 상태 거부로 변경
    join_request.status = "rejected"
    join_request.processed_at = datetime.utcnow()
    db.add(join_request)

    await db.commit()
    return {"message": "가입 요청이 거부되었습니다."}

@router.post("/kick")
async def kick_workspace_member(
    request_data: WorkspaceKickRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 1. 워크스페이스 조회
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="해당 워크스페이스를 찾을 수 없습니다.")

    # 2. 관리자 권한 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.is_workspace_admin == True
    ))
    admin = result.scalars().first()
    if not admin:
        raise HTTPException(status_code=403, detail="관리자만 멤버를 추방할 수 있습니다.")

    # 3. 추방 대상 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == request_data.user_id,
        WorkspaceMember.workspace_id == workspace.id
    ))
    target_member = result.scalars().first()
    if not target_member:
        raise HTTPException(status_code=404, detail="추방 대상 사용자는 워크스페이스의 멤버가 아닙니다.")

    # 4. 자기 자신 추방 방지
    if request_data.user_id == user_context["user_id"]:
        raise HTTPException(status_code=400, detail="자기 자신은 추방할 수 없습니다.")

    # ✅ 5. 채널 멤버에서 해당 사용자 전부 삭제
    await db.execute(
        ChannelMember.__table__.delete().where(
            ChannelMember.user_id == request_data.user_id,
            ChannelMember.channel_id.in_(
                select(Channel.id).where(Channel.workspace_id == workspace.id)
            )
        )
    )

    # ✅ 6. 워크스페이스 멤버 삭제
    await db.delete(target_member)

    # 7. 커밋
    await db.commit()

    return {"message": "해당 사용자를 워크스페이스 및 채널에서 추방했습니다."}

@router.get("/roles", response_model=List[dict])
async def get_roles(
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    """
    모든 역할 목록을 가져옵니다.
    """
    result = await db.execute(select(Role).order_by(Role.level))
    roles = result.scalars().all()
    
    return [
        {
            "id": role.id,
            "name": role.name,
            "level": role.level
        }
        for role in roles
    ]
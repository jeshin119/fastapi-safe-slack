from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.models import User, Channel, ChannelMember, WorkspaceMember, Workspace, Role
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelJoinRequestResponse, ChannelJoinRequest, ChannelApproveRequest
from app.core.utils import get_current_user, get_current_user_with_context, check_user_permission_by_name
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=ChannelResponse)
async def create_channel(
    channel_data: ChannelCreate,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        channel_data.workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == channel_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # 채널명 중복 확인
    result = await db.execute(select(Channel).where(
        Channel.name == channel_data.name,
        Channel.workspace_id == workspace.id
    ))
    existing_channel = result.scalars().first()
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 채널명입니다."
        )
    
    channel = Channel(
        name=channel_data.name,
        workspace_id=workspace.id,
        created_by=user_context["user_id"],  # 토큰에서 user_id 사용
        is_public=channel_data.is_public
    )
    db.add(channel)
    await db.flush()
    
    if channel_data.is_public:
        member = ChannelMember(
            user_id=user_context["user_id"],  # 토큰에서 user_id 사용
            channel_id=channel.id,
            status="approved"
        )
        db.add(member)
    
    await db.commit()
    await db.refresh(channel)
    
    return {
        "name": channel.name,
        "workspace_name": channel_data.workspace_name,
        "is_public": channel.is_public
    }

@router.post("/join-request", response_model=ChannelJoinRequestResponse)
async def request_channel_join(
    request_data: ChannelJoinRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        request_data.workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == request_data.channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 공개 채널인 경우 바로 입장
    if channel.is_public:
        result = await db.execute(select(ChannelMember).where(
            ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
            ChannelMember.channel_id == channel.id
        ))
        existing_member = result.scalars().first()
        if not existing_member:
            member = ChannelMember(
                user_id=user_context["user_id"],  # 토큰에서 user_id 사용
                channel_id=channel.id,
                status="approved"
            )
            db.add(member)
            await db.commit()
        return {"message": "채널에 입장했습니다."}
    
    # 비공개 채널인 경우 기존 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        if existing_member.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 채널 멤버입니다."
            )
        elif existing_member.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 입장 요청이 대기 중입니다."
            )
    
    # 입장 요청 생성
    member = ChannelMember(
        user_id=user_context["user_id"],  # 토큰에서 user_id 사용
        channel_id=channel.id,
        status="pending"
    )
    db.add(member)
    await db.commit()
    return {"message": "채널 관리자에게 입장 요청이 전송되었습니다."}

@router.post("/approve", response_model=ChannelJoinRequestResponse)
async def approve_channel_join(
    approve_data: ChannelApproveRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        approve_data.workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == approve_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    # channel_name으로 channel_id 찾기
    result = await db.execute(select(Channel).where(
        Channel.name == approve_data.channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 현재 사용자가 채널 멤버인지 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    current_membership = result.scalars().first()
    if not current_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # user_email로 사용자 찾기
    result = await db.execute(select(User).where(User.email == approve_data.user_email))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 자기 자신을 승인하려는 경우 체크
    if target_user.email == user_context["user_email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신을 승인할 수 없습니다."
        )
    
    # 대기 중인 입장 요청 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == target_user.id,
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "pending"
    ))
    target_membership = result.scalars().first()
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대기 중인 입장 요청을 찾을 수 없습니다."
        )
    
    # 입장 승인
    target_membership.status = "approved"
    await db.commit()
    return {"message": "채널 입장이 승인되었습니다."}

@router.get("/{channel_name}/info")
async def get_channel_info(
    channel_name: str,
    workspace_name: str,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
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
    
    # 현재 사용자가 채널 멤버인지 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 채널 생성자 정보 조회
    creator_name = "Unknown"
    if channel.created_by:
        result = await db.execute(select(User).where(User.id == channel.created_by))
        creator = result.scalars().first()
        if creator:
            creator_name = creator.name
    
    return {
        "name": channel.name,
        "workspace_name": workspace_name,
        "is_public": channel.is_public,
        "is_default": channel.is_default,
        "created_by": creator_name,
        "created_at": channel.created_at
    }

@router.get("/{channel_name}/members")
async def get_channel_members(
    channel_name: str,
    workspace_name: str,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 토큰에서 워크스페이스 권한 확인 (DB 조회 없이)
    has_permission = await check_user_permission_by_name(
        user_context, 
        workspace_name
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="워크스페이스에 접근할 권한이 없습니다."
        )
    
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
    
    # 현재 사용자가 채널 멤버인지 확인 (토큰에서 user_id 사용)
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],  # 토큰에서 user_id 사용
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널에 접근할 권한이 없습니다."
        )
    
    # 채널 멤버 정보 조회 (JOIN으로 한 번에 가져오기)
    result = await db.execute(
        select(ChannelMember, User)
        .join(User, ChannelMember.user_id == User.id)
        .where(
            ChannelMember.channel_id == channel.id,
            ChannelMember.status == "approved"
        )
    )
    members_data = result.all()
    
    return [
        {
            "user_email": user.email,
            "user_name": user.name,
            "joined_at": member.created_at if hasattr(member, 'created_at') else None
        }
        for member, user in members_data
    ] 
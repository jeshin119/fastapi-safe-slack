from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from app.db.session import get_db
from app.models.models import User, Channel, ChannelMember, WorkspaceMember, Workspace, Role
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelJoinRequestResponse, ChannelJoinRequest, ChannelApproveRequest
from app.core.utils import get_current_user_with_context
from app.core.business_utils import create_channel_with_creator
from datetime import datetime
from typing import List
from pydantic import BaseModel
from app.models.models import RequestStatus
from app.models.models import File
from app.core.dynamodb import dynamodb_manager
from app.core.date_utils import get_current_datetime

router = APIRouter()

class ChannelCreateRequest(BaseModel):
    workspace_name: str
    channel_name: str
    is_public: bool = True

class ChannelListRequest(BaseModel):
    workspace_name: str

class ChannelJoinRequestRequest(BaseModel):
    workspace_name: str
    channel_name: str

class ChannelRequestListRequest(BaseModel):
    workspace_name: str

class ChannelApproveRequestRequest(BaseModel):
    workspace_name: str
    request_id: int
    request_user_name: str
    request_role_name: str
    channel_name: str

class ChannelMembersListRequest(BaseModel):
    workspace_name: str
    channel_name: str

class ChannelLeaveRequest(BaseModel):
    workspace_name: str
    channel_name: str

class ChannelJoinRequestListItem(BaseModel):
    request_id: int
    user_email: str
    user_name: str
    role_name: str
    status: str
    channel_name: str

class ChannelMemberListItem(BaseModel):
    user_id: int
    name: str
    email: str
    role_name: str
    is_admin: bool

@router.post("/create")
async def create_channel(
    channel_data: ChannelCreateRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    result = await create_channel_with_creator(db, channel_data.workspace_name, channel_data.channel_name, user_context["user_id"], channel_data.is_public)
    return result

@router.post("/list")
async def get_channels(
    request_data: ChannelListRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 1. 워크스페이스 조회
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )

    user_id = user_context["user_id"]

    # 2. 사용자가 이미 가입한 채널 ID 목록 조회
    result = await db.execute(
        select(Channel.id)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(
            ChannelMember.user_id == user_id,
            ChannelMember.status == RequestStatus.APPROVED,
            Channel.workspace_id == workspace.id
        )
    )
    joined_channel_ids = [row[0] for row in result.all()]

    # 3. 아직 가입하지 않은 공개 채널 조회
    result = await db.execute(
        select(Channel)
        .where(
            Channel.workspace_id == workspace.id,
            Channel.is_public == True,
            ~Channel.id.in_(joined_channel_ids)
        )
    )
    public_channels_to_join = result.scalars().all()

    # 4. 해당 공개 채널에 자동 가입 처리
    for channel in public_channels_to_join:
        new_member = ChannelMember(
            user_id=user_id,
            channel_id=channel.id,
            status=RequestStatus.APPROVED
        )
        db.add(new_member)

    # 5. DB에 저장
    await db.commit()
    
    # 6. 공개 채널 자동 가입 시 입장 메시지 브로드캐스트
    try:
        from app.core.websocket_manager import manager
        # 사용자 정보 조회
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        
        for channel in public_channels_to_join:
            await manager.broadcast_to_channel(
                workspace.id,
                channel.id,
                {
                    "type": "user_joined",
                    "user_id": user_id,
                    "user_name": user.name if user else "Unknown",
                    "message": f"{user.name if user else 'Unknown'}님이 채널에 가입하셨습니다.",
                    "timestamp": get_current_datetime().isoformat()
                }
            )
    except Exception as e:
        print(f"공개 채널 자동 가입 입장 메시지 브로드캐스트 실패: {e}")
        # WebSocket 오류가 있어도 가입은 성공으로 처리

    # 7. 모든 가입된 채널을 다시 조회
    result = await db.execute(
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(
            ChannelMember.user_id == user_id,
            ChannelMember.status == RequestStatus.APPROVED,
            Channel.workspace_id == workspace.id
        )
    )
    all_joined_channels = result.scalars().all()

    # 8. 반환
    return [
        {
            "channel_id": ch.id,
            "name": ch.name,
            "is_public": ch.is_public
        }
        for ch in all_joined_channels
    ]

@router.delete("/{channel_name}")
async def delete_channel(
    channel_name: str,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 모든 워크스페이스에서 해당 이름의 채널 찾기
    result = await db.execute(select(Channel).where(Channel.name == channel_name))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채널을 찾을 수 없습니다."
        )
    
    # 채널 생성자 확인
    if channel.created_by != user_context["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널 생성자만 삭제할 수 있습니다."
        )
    
    # 연관된 데이터 먼저 삭제
    # 1. 채널 멤버 삭제
    result = await db.execute(select(ChannelMember).where(ChannelMember.channel_id == channel.id))
    channel_members = result.scalars().all()
    for member in channel_members:
        await db.delete(member)
    
    # 2. 메시지 삭제
    result = await db.execute(select(File).where(File.channel_id == channel.id))
    files = result.scalars().all()
    for file in files:
        await db.delete(file)
    
    # 4. 채널 삭제
    await db.delete(channel)
    await db.commit()
    
    return {"message": "채널이 삭제되었습니다."}

@router.post("/join-request")
async def request_channel_join(
    request_data: ChannelJoinRequestRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
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
            ChannelMember.user_id == user_context["user_id"],
            ChannelMember.channel_id == channel.id
        ))
        existing_member = result.scalars().first()
        if not existing_member:
            member = ChannelMember(
                user_id=user_context["user_id"],
                channel_id=channel.id,
                status="approved"
            )
            db.add(member)
            await db.commit()
        return {"message": "채널에 입장했습니다."}
    
    # 비공개 채널인 경우 기존 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id
    ))
    existing_member = result.scalars().first()
    if existing_member:
        if existing_member.status == RequestStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 채널 멤버입니다."
            )
        elif existing_member.status == RequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 입장 요청이 대기 중입니다."
            )
    
    # 입장 요청 생성
    member = ChannelMember(
        user_id=user_context["user_id"],
        channel_id=channel.id,
        status=RequestStatus.PENDING
    )
    db.add(member)
    await db.commit()
    return {"message": "채널 관리자에게 입장 요청이 전송되었습니다."}

@router.post("/request_list")
async def get_channel_join_requests(
    request_data: ChannelRequestListRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # workspace_name으로 workspace_id 찾기
    result = await db.execute(select(Workspace).where(Workspace.name == request_data.workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스가 없습니다."
        )
    
    # 현재 사용자가 관리자인 채널들의 입장 요청 조회
    result = await db.execute(
        select(ChannelMember, User, WorkspaceMember, Role, Channel)
        .join(User, ChannelMember.user_id == User.id)
        .join(WorkspaceMember, and_(
            User.id == WorkspaceMember.user_id,
            WorkspaceMember.workspace_id == workspace.id
        ))
        .join(Role, WorkspaceMember.role_id == Role.id)
        .join(Channel, ChannelMember.channel_id == Channel.id)
        .where(
            Channel.workspace_id == workspace.id,
            ChannelMember.status == RequestStatus.PENDING,
            Channel.created_by == user_context["user_id"]
        )
    )
    requests_data = result.all()
    
    return [
        {
            "request_id": member.id,
            "user_email": user.email,
            "user_name": user.name,
            "role_name": role.name,
            "status": member.status,
            "channel_name": channel.name
        }
        for member, user, workspace_member, role, channel in requests_data
    ]

@router.post("/approve")
async def approve_channel_join(
    approve_data: ChannelApproveRequestRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
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
    
    # 현재 사용자가 채널 생성자인지 확인
    if channel.created_by != user_context["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널 생성자만 입장을 승인할 수 있습니다."
        )
    
    # 입장 요청 조회
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.id == approve_data.request_id,
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == RequestStatus.PENDING
    ))
    request = result.scalars().first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="입장 요청을 찾을 수 없습니다."
        )
    
    # 입장 승인
    request.status = RequestStatus.APPROVED
    await db.commit()
    
    # 승인된 사용자 정보 조회
    result = await db.execute(select(User).where(User.id == request.user_id))
    approved_user = result.scalars().first()
    
    # WebSocket을 통해 채널에 입장 메시지 브로드캐스트
    try:
        from app.core.websocket_manager import manager
        await manager.broadcast_to_channel(
            workspace.id,
            channel.id,
            {
                "type": "user_joined",
                "user_id": request.user_id,
                "user_name": approved_user.name if approved_user else "Unknown",
                "message": f"{approved_user.name if approved_user else 'Unknown'}님이 채널에 가입하셨습니다.",
                "timestamp": get_current_datetime().isoformat()
            }
        )
    except Exception as e:
        print(f"입장 메시지 브로드캐스트 실패: {e}")
        # WebSocket 오류가 있어도 승인은 성공으로 처리
    
    return {"message": "채널 입장이 승인되었습니다."}

@router.post("/members_list")
async def get_channel_members(
    request_data: ChannelMembersListRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
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
    
    # 현재 사용자가 채널 멤버인지 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == RequestStatus.APPROVED
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="채널 멤버만 멤버 목록을 볼 수 있습니다."
        )
    
    # 채널 멤버 정보 조회 (JOIN으로 한 번에 가져오기)
    result = await db.execute(
        select(ChannelMember, User, WorkspaceMember, Role)
        .join(User, ChannelMember.user_id == User.id)
        .join(WorkspaceMember, User.id == WorkspaceMember.user_id)
        .join(Role, WorkspaceMember.role_id == Role.id)
        .where(
            ChannelMember.channel_id == channel.id,
            ChannelMember.status == RequestStatus.APPROVED,
            WorkspaceMember.workspace_id == workspace.id
        )
    )
    members_data = result.all()
    
    return [
        {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "role_name": role.name,
            "is_admin": channel.created_by == user.id
        }
        for member, user, workspace_member, role in members_data
    ]

@router.post("/leave")
async def leave_channel(
    request_data: ChannelLeaveRequest,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
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
    
    # 현재 사용자의 채널 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == RequestStatus.APPROVED
    ))
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="채널 멤버가 아닙니다."
        )
    
    # 채널 생성자인 경우, 다른 멤버가 있는지 확인
    if channel.created_by == user_context["user_id"]:
        # 채널의 총 멤버 수 확인
        result = await db.execute(select(ChannelMember).where(
            ChannelMember.channel_id == channel.id,
            ChannelMember.status == RequestStatus.APPROVED
        ))
        all_members = result.scalars().all()
        
        # 자기밖에 없으면 나갈 수 있음
        if len(all_members) == 1:
            # 채널 삭제 (연관된 데이터도 함께 삭제)
            # 1. 채널 멤버 삭제
            result = await db.execute(select(ChannelMember).where(ChannelMember.channel_id == channel.id))
            channel_members = result.scalars().all()
            for member in channel_members:
                await db.delete(member)
            
            # 2. DynamoDB에서 메시지 삭제
            try:
                await dynamodb_manager.delete_channel_messages(channel.id)
            except Exception as e:
                # DynamoDB 삭제 실패해도 계속 진행
                print(f"DynamoDB 메시지 삭제 실패: {e}")
            
            # 3. 파일 삭제
            result = await db.execute(select(File).where(File.channel_id == channel.id))
            files = result.scalars().all()
            for file in files:
                await db.delete(file)
            
            # 4. 채널 삭제
            await db.delete(channel)
            await db.commit()
            
            return {"message": "채널에서 나갔습니다. (마지막 멤버였으므로 채널이 삭제되었습니다.)"}
        else:
            # 다른 멤버가 있으면 나갈 수 없음
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="채널 생성자는 다른 멤버가 있을 때는 채널을 나갈 수 없습니다."
            )
    
    # 일반 멤버는 바로 나가기
    await db.delete(membership)
    await db.commit()
    
    return {"message": "채널에서 나갔습니다."} 
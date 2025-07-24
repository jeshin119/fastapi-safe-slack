from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.utils import get_current_user_with_context
from app.core.websocket_manager import manager
from app.models.models import Workspace, Channel, WorkspaceMember, ChannelMember, Message, User
from app.schemas.chat import WebSocketMessage
from datetime import datetime
import json

router = APIRouter()

@router.websocket("/ws/{workspace_name}/{channel_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    workspace_name: str,
    channel_name: str,
    token: str = None
):
    # JWT 토큰 검증
    if not token:
        await websocket.close(code=4001, reason="토큰이 필요합니다.")
        return
    
    try:
        # 토큰에서 사용자 정보 추출 (간단한 방식)
        # 실제로는 JWT 디코딩 로직 필요
        user_context = await get_current_user_with_context(token)
    except:
        await websocket.close(code=4001, reason="유효하지 않은 토큰입니다.")
        return
    
    # 데이터베이스 연결
    db = await get_db().__anext__()
    
    try:
        # 워크스페이스 확인
        result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
        workspace = result.scalars().first()
        if not workspace:
            await websocket.close(code=4004, reason="워크스페이스를 찾을 수 없습니다.")
            return
        
        # 채널 확인
        result = await db.execute(select(Channel).where(
            Channel.name == channel_name,
            Channel.workspace_id == workspace.id
        ))
        channel = result.scalars().first()
        if not channel:
            await websocket.close(code=4004, reason="채널을 찾을 수 없습니다.")
            return
        
        # 워크스페이스 멤버십 확인
        result = await db.execute(select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_context["user_id"],
            WorkspaceMember.workspace_id == workspace.id
        ))
        workspace_membership = result.scalars().first()
        if not workspace_membership:
            await websocket.close(code=4003, reason="워크스페이스에 접근할 권한이 없습니다.")
            return
        
        # 채널 멤버십 확인
        result = await db.execute(select(ChannelMember).where(
            ChannelMember.user_id == user_context["user_id"],
            ChannelMember.channel_id == channel.id,
            ChannelMember.status == "approved"
        ))
        channel_membership = result.scalars().first()
        if not channel_membership:
            await websocket.close(code=4003, reason="채널에 접근할 권한이 없습니다.")
            return
        
        # WebSocket 연결
        await manager.connect(
            websocket, 
            workspace.id, 
            channel.id, 
            user_context["user_id"], 
            user_context["user_name"]
        )
        
        # 연결된 사용자 목록 전송
        connected_users = manager.get_connected_users(workspace.id, channel.id)
        await manager.send_personal_message(websocket, {
            "type": "connected_users",
            "connected_users": connected_users,
            "timestamp": datetime.now().isoformat()
        })
        
        # 메시지 수신 루프
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # 메시지 타입에 따른 처리
                if message_data.get("type") == "message":
                    content = message_data.get("content", "").strip()
                    if not content:
                        continue
                    
                    # 메시지 DB 저장
                    new_message = Message(
                        content=content,
                        user_id=user_context["user_id"],
                        channel_id=channel.id,
                        message_type=message_data.get("message_type", "text"),
                        reply_to=message_data.get("reply_to"),
                        mentions=json.dumps(message_data.get("mentions", [])) if message_data.get("mentions") else None
                    )
                    
                    db.add(new_message)
                    await db.commit()
                    await db.refresh(new_message)
                    
                    # 채널 멤버들에게 메시지 브로드캐스트
                    await manager.broadcast_to_channel(
                        workspace.id,
                        channel.id,
                        {
                            "type": "message",
                            "message_id": new_message.id,
                            "content": content,
                            "user_id": user_context["user_id"],
                            "user_name": user_context["user_name"],
                            "message_type": message_data.get("message_type", "text"),
                            "reply_to": message_data.get("reply_to"),
                            "mentions": message_data.get("mentions"),
                            "timestamp": new_message.created_at.isoformat()
                        }
                    )
                
                elif message_data.get("type") == "typing":
                    # 타이핑 상태 브로드캐스트
                    await manager.broadcast_to_channel(
                        workspace.id,
                        channel.id,
                        {
                            "type": "typing",
                            "user_id": user_context["user_id"],
                            "user_name": user_context["user_name"],
                            "timestamp": datetime.now().isoformat()
                        },
                        exclude_websocket=websocket
                    )
                
                elif message_data.get("type") == "read_receipt":
                    # 읽음 확인 처리 (추후 구현)
                    pass
                    
            except json.JSONDecodeError:
                # 잘못된 JSON 형식
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "잘못된 메시지 형식입니다.",
                    "timestamp": datetime.now().isoformat()
                })
                
    except WebSocketDisconnect:
        # 연결 해제 처리
        await manager.disconnect(websocket)
    except Exception as e:
        # 기타 오류 처리
        await manager.send_personal_message(websocket, {
            "type": "error",
            "message": f"오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
        await manager.disconnect(websocket)
    finally:
        await db.close()

# REST API 엔드포인트 (메시지 히스토리 조회)
@router.get("/workspaces/{workspace_name}/channels/{channel_name}/messages")
async def get_message_history(
    workspace_name: str,
    channel_name: str,
    limit: int = 50,
    offset: int = 0,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 워크스페이스 확인
    result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없습니다.")
    
    # 채널 확인
    result = await db.execute(select(Channel).where(
        Channel.name == channel_name,
        Channel.workspace_id == workspace.id
    ))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    
    # 권한 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(status_code=403, detail="워크스페이스에 접근할 권한이 없습니다.")
    
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    channel_membership = result.scalars().first()
    if not channel_membership:
        raise HTTPException(status_code=403, detail="채널에 접근할 권한이 없습니다.")
    
    # 메시지 히스토리 조회
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()
    
    # 사용자 정보 조회
    user_ids = list(set([msg.user_id for msg in messages]))
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {user.id: user for user in result.scalars().all()}
    
    # 응답 데이터 구성
    message_list = []
    for msg in reversed(messages):  # 최신순으로 정렬
        user = users.get(msg.user_id)
        message_list.append({
            "message_id": msg.id,
            "content": msg.content,
            "user_id": msg.user_id,
            "user_name": user.name if user else "알 수 없음",
            "message_type": msg.message_type,
            "reply_to": msg.reply_to,
            "mentions": json.loads(msg.mentions) if msg.mentions else None,
            "timestamp": msg.created_at.isoformat(),
            "workspace_id": workspace.id,
            "channel_id": channel.id
        })
    
    return {
        "messages": message_list,
        "total": len(message_list),
        "has_more": len(messages) == limit
    } 
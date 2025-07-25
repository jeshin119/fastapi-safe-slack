from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.utils import get_current_user_with_context, verify_token
from app.core.websocket_manager import manager
from app.models.models import Workspace, Channel, WorkspaceMember, ChannelMember, User
from app.core.dynamodb import dynamodb_manager
from app.schemas.chat import WebSocketMessage
from datetime import datetime
import json

router = APIRouter()

def verify_websocket_token(token: str) -> dict:
    """
    WebSocket용 JWT 토큰 검증 함수
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return payload

@router.websocket("/ws/{workspace_name}/{channel_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    workspace_name: str,
    channel_name: str,
    token: str = None
):
    # 개발 모드 토큰 처리
    if token == "dev-token":
        user_context = {
            "user_id": 1,
            "user_name": "김개발",
            "email": "kim@example.com"
        }
        # 개발 모드용 더미 데이터
        workspace = type('Workspace', (), {'id': 1})()
        channel = type('Channel', (), {'id': 1})()
        db = None
    else:
        # JWT 토큰 검증
        if not token:
            await websocket.close(code=4001, reason="토큰이 필요합니다.")
            return
        
        try:
            # WebSocket용 토큰 검증
            user_context = verify_websocket_token(token)
        except Exception as e:
            await websocket.close(code=4001, reason="유효하지 않은 토큰입니다.")
            return
        
        # 데이터베이스 연결 (워크스페이스/채널 검증용)
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
        except Exception as e:
            await websocket.close(code=4005, reason=f"데이터베이스 오류: {str(e)}")
            return
    
    try:
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
                    
                    # message_type 검증
                    message_type = message_data.get("message_type", "text")
                    valid_message_types = ["text", "file", "image", "video", "audio"]
                    if message_type not in valid_message_types:
                        await manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": f"유효하지 않은 메시지 타입입니다. 허용된 타입: {', '.join(valid_message_types)}",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # DynamoDB에 메시지 저장 (개발 모드에서는 건너뛰기)
                    if token != "dev-token":
                        message_item = {
                            'channel_id': channel.id,
                            'user_id': user_context["user_id"],
                            'user_name': user_context["user_name"],
                            'content': content,
                            'message_type': message_type,
                            'reply_to': message_data.get('reply_to'),
                            'mentions': message_data.get('mentions', [])
                        }
                        
                        try:
                            message_id = await dynamodb_manager.save_message(message_item)
                            print(f"DynamoDB 메시지 저장 성공: {message_id}")
                        except Exception as e:
                            print(f"DynamoDB 메시지 저장 실패: {e}")
                            # DynamoDB 저장 실패해도 실시간 채팅은 계속 진행
                            message_id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    else:
                        # 개발 모드에서는 임시 메시지 ID 생성
                        message_id = f"dev_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    
                    # 채널 멤버들에게 메시지 브로드캐스트
                    await manager.broadcast_to_channel(
                        workspace.id,
                        channel.id,
                        {
                            "type": "message",
                            "message_id": message_id,
                            "content": content,
                            "user_id": user_context["user_id"],
                            "user_name": user_context["user_name"],
                            "message_type": message_type,
                            "reply_to": message_data.get("reply_to"),
                            "mentions": message_data.get("mentions"),
                            "timestamp": datetime.now().isoformat()
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
    finally:
        if db:
            await db.close()

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
    
    # 워크스페이스 멤버십 확인
    result = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == user_context["user_id"],
        WorkspaceMember.workspace_id == workspace.id
    ))
    workspace_membership = result.scalars().first()
    if not workspace_membership:
        raise HTTPException(status_code=403, detail="워크스페이스에 접근할 권한이 없습니다.")
    
    # 채널 멤버십 확인
    result = await db.execute(select(ChannelMember).where(
        ChannelMember.user_id == user_context["user_id"],
        ChannelMember.channel_id == channel.id,
        ChannelMember.status == "approved"
    ))
    channel_membership = result.scalars().first()
    if not channel_membership:
        raise HTTPException(status_code=403, detail="채널에 접근할 권한이 없습니다.")
    
    # DynamoDB에서 메시지 조회
    messages = await dynamodb_manager.get_messages(channel.id, limit)
    
    # 응답 형식 변환
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "message_id": msg["message_id"],
            "content": msg["content"],
            "user_id": msg["user_id"],
            "user_name": msg["user_name"],
            "message_type": msg.get("message_type", "text"),
            "timestamp": msg["timestamp"],
            "reply_to": msg.get("reply_to"),
            "mentions": json.loads(msg["mentions"]) if msg.get("mentions") else []
        })
    
    return formatted_messages 
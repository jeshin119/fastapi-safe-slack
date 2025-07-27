from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.utils import get_current_user_with_context, verify_token
from app.core.websocket_manager import manager
from app.models.models import Workspace, Channel, WorkspaceMember, ChannelMember, User
from app.core.dynamodb import dynamodb_manager
from app.schemas.chat import WebSocketMessage
from app.core.db_utils import get_workspace_by_name, get_channel_by_name, get_workspace_membership, get_channel_membership
from app.core.permission_utils import verify_channel_access
from app.core.date_utils import get_current_datetime, get_hours_ago
from datetime import datetime
import json
from jose.exceptions import JWTError

router = APIRouter()

def verify_websocket_token(token: str) -> dict:
    """
    WebSocket용 JWT 토큰 검증 함수
    """
    try:
        payload = verify_token(token)
        if payload is None:
            print(f"❌ 토큰 검증 실패: verify_token이 None 반환")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        print(f"✅ 토큰 검증 성공: payload={payload}")
        return payload
    except JWTError as e:
        print(f"❌ JWT 디코딩 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT decode error: {str(e)}"
        )
    except Exception as e:
        print(f"❌ 토큰 검증 중 예상치 못한 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation error: {str(e)}"
        )

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
        # WebSocket용 토큰 검증
        user_context = verify_websocket_token(token)
        print(f"🔍 WebSocket 토큰 검증 성공: user_id={user_context.get('user_id')}, user_name={user_context.get('user_name')}")
    except Exception as e:
        print(f"❌ WebSocket 토큰 검증 실패: {e}")
        await websocket.close(code=4001, reason="유효하지 않은 토큰입니다.")
        return
    
    # 데이터베이스 세션 직접 생성
    from app.db.session import AsyncSessionLocal
    db = AsyncSessionLocal()
    
    try:
        # 워크스페이스와 채널 접근 권한 확인
        workspace = await get_workspace_by_name(db, workspace_name)
        print(f"✅ 워크스페이스 확인 성공: {workspace_name} (ID: {workspace.id})")
        
        channel = await get_channel_by_name(db, channel_name, workspace.id)
        print(f"✅ 채널 확인 성공: {channel_name} (ID: {channel.id})")
        
        # 워크스페이스 멤버십 확인
        workspace_membership = await get_workspace_membership(db, user_context["user_id"], workspace.id)
        if not workspace_membership:
            print(f"❌ 워크스페이스 멤버십 없음: user_id={user_context['user_id']}, workspace_id={workspace.id}")
            await websocket.close(code=4003, reason="워크스페이스에 접근할 권한이 없습니다.")
            return
        print(f"✅ 워크스페이스 멤버십 확인 성공: user_id={user_context['user_id']}")
        
        # 채널 멤버십 확인
        channel_membership = await get_channel_membership(db, user_context["user_id"], channel.id)
        if not channel_membership:
            print(f"❌ 채널 멤버십 없음: user_id={user_context['user_id']}, channel_id={channel.id}")
            await websocket.close(code=4003, reason="채널에 접근할 권한이 없습니다.")
            return
        print(f"✅ 채널 멤버십 확인 성공: user_id={user_context['user_id']}")
        
    except Exception as e:
        print(f"❌ 데이터베이스 오류: {e}")
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
        
        # 새로 가입한 유저가 아닌 경우 이전 채팅 내용 전송
        # 채널 멤버십 가입 시간 확인 (24시간 이내면 새 멤버로 간주)
        one_day_ago = get_hours_ago(24)
        
        if channel_membership.joined_at and channel_membership.joined_at < one_day_ago:
            print(f"📚 기존 멤버 ({user_context['user_name']})에게 메시지 히스토리 전송")
            try:
                # DynamoDB에서 최근 메시지 50개 조회
                messages = await dynamodb_manager.get_messages(channel.id, limit=50)
                
                if messages:
                    # 메시지 히스토리 전송
                    await manager.send_personal_message(websocket, {
                        "type": "message_history",
                        "messages": messages,
                        "timestamp": get_current_datetime().isoformat()
                    })
                    print(f"✅ 메시지 히스토리 전송 완료: {len(messages)}개 메시지")
                else:
                    print("📭 메시지 히스토리가 없습니다.")
                    
            except Exception as e:
                print(f"❌ 메시지 히스토리 조회 실패: {e}")
                # 히스토리 조회 실패해도 실시간 채팅은 계속 진행
        else:
            print(f"🆕 새 멤버 ({user_context['user_name']}) - 메시지 히스토리 전송 건너뜀")
        
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
                            "timestamp": get_current_datetime().isoformat()
                        })
                        continue
                    
                    # DynamoDB에 메시지 저장
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
                        message_id = f"temp_{get_current_datetime().strftime('%Y%m%d_%H%M%S_%f')}"
                    
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
                            "timestamp": get_current_datetime().isoformat()
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
                            "timestamp": get_current_datetime().isoformat()
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
                    "timestamp": get_current_datetime().isoformat()
                })
            except Exception as e:
                # 기타 오류 처리
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"메시지 처리 중 오류가 발생했습니다: {str(e)}",
                    "timestamp": get_current_datetime().isoformat()
                })
                
    except WebSocketDisconnect:
        # WebSocket 연결 해제 처리
        manager.disconnect(websocket)
    except Exception as e:
        # 기타 예외 처리
        print(f"WebSocket 오류: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        # 데이터베이스 세션 정리
        if db:
            try:
                await db.close()
            except Exception as e:
                print(f"데이터베이스 세션 정리 오류: {e}")

@router.get("/workspaces/{workspace_name}/channels/{channel_name}/messages")
async def get_message_history(
    workspace_name: str,
    channel_name: str,
    limit: int = 50,
    offset: int = 0,
    user_context: dict = Depends(get_current_user_with_context),
    db: AsyncSession = Depends(get_db)
):
    # 워크스페이스와 채널 접근 권한 확인
    workspace, channel = await verify_channel_access(db, user_context["user_id"], workspace_name, channel_name)
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
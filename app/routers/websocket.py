from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.workspace import Workspace
from app.models.channel import Channel
from app.core.websocket_manager import manager
from app.core.utils import verify_token
import json
from jose.exceptions import JWTError

router = APIRouter()

def verify_websocket_token(token: str) -> dict:
    """WebSocket용 JWT 토큰 검증 함수"""
    try:
        payload = verify_token(token)
        if payload is None:
            print(f"❌ 토큰 검증 실패: verify_token이 None 반환")
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
        print(f"✅ 토큰 검증 성공: payload={payload}")
        return payload
    except JWTError as e:
        print(f"❌ JWT 디코딩 오류: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"JWT decode error: {str(e)}"
        )
    except Exception as e:
        print(f"❌ 토큰 검증 중 예상치 못한 오류: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Token validation error: {str(e)}"
        )

@router.websocket("/ws/{workspace_name}/{channel_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    workspace_name: str,
    channel_name: str,
    token: str = None
):
    """
    WebSocket 연결 엔드포인트 (chat.py 방식)
    URL 예시: ws://localhost:8000/ws/my-workspace/general?token=your_jwt_token
    """
    
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
    db = AsyncSessionLocal()
    
    try:
        # 워크스페이스 조회
        from sqlalchemy import select
        result = await db.execute(select(Workspace).where(Workspace.name == workspace_name))
        workspace = result.scalars().first()
        if not workspace:
            await websocket.close(code=4004, reason="Workspace not found")
            return
        
        # 채널 조회
        result = await db.execute(select(Channel).where(
            Channel.name == channel_name,
            Channel.workspace_id == workspace.id
        ))
        channel = result.scalars().first()
        if not channel:
            await websocket.close(code=4004, reason="Channel not found")
            return
        
        # 워크스페이스 멤버십 확인
        from app.models.workspace import WorkspaceMember
        result = await db.execute(select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_context["user_id"],
            WorkspaceMember.workspace_id == workspace.id
        ))
        workspace_membership = result.scalars().first()
        if not workspace_membership:
            await websocket.close(code=4003, reason="워크스페이스에 접근할 권한이 없습니다.")
            return
        
        # 채널 멤버십 확인
        from app.models.channel import ChannelMember
        result = await db.execute(select(ChannelMember).where(
            ChannelMember.user_id == user_context["user_id"],
            ChannelMember.channel_id == channel.id,
            ChannelMember.status == "approved"
        ))
        channel_membership = result.scalars().first()
        if not channel_membership:
            await websocket.close(code=4003, reason="채널에 접근할 권한이 없습니다.")
            return
        
        # WebSocket 연결 관리자에 등록
        await manager.connect(
            websocket, 
            workspace.id, 
            channel.id, 
            user_context["user_id"], 
            user_context.get("user_name") or user_context.get("user_email")
        )
        
        # 메시지 수신 루프
        while True:
            try:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # 메시지 타입에 따른 처리
                message_type = message_data.get("type", "message")
                
                if message_type == "message":
                    # 일반 채팅 메시지
                    content = message_data.get("content", "")
                    if content.strip():
                        # DynamoDB에 메시지 저장
                        from app.core.dynamodb import dynamodb_manager
                        message_item = {
                            'channel_id': channel.id,
                            'user_id': user_context["user_id"],
                            'user_name': user_context.get("user_name") or user_context.get("user_email"),
                            'content': content,
                            'message_type': message_data.get("message_type", "text"),
                            'reply_to': message_data.get('reply_to'),
                            'mentions': message_data.get('mentions', [])
                        }
                        
                        try:
                            message_id = await dynamodb_manager.save_message(message_item)
                            print(f"DynamoDB 메시지 저장 성공: {message_id}")
                        except Exception as e:
                            print(f"DynamoDB 메시지 저장 실패: {e}")
                            message_id = f"temp_{message_data.get('timestamp', 'unknown')}"
                        
                        await manager.broadcast_to_channel(
                            workspace.id,
                            channel.id,
                            {
                                "type": "new_message",
                                "message_id": message_id,
                                "content": content,
                                "user_id": user_context["user_id"],
                                "user_name": user_context.get("user_name") or user_context.get("user_email"),
                                "user_email": user_context.get("user_email"),
                                "message_type": message_data.get("message_type", "text"),
                                "timestamp": message_data.get("timestamp")
                            }
                        )
                
                elif message_type == "typing":
                    # 타이핑 상태 알림
                    await manager.broadcast_to_channel(
                        workspace.id,
                        channel.id,
                        {
                            "type": "user_typing",
                            "user_id": user_context["user_id"],
                            "user_name": user_context.get("user_name") or user_context.get("user_email"),
                            "is_typing": message_data.get("is_typing", False)
                        },
                        exclude_websocket=websocket
                    )
                
                elif message_type == "ping":
                    # 연결 상태 확인
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                        "timestamp": message_data.get("timestamp")
                    })
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # 잘못된 JSON 형식
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                # 기타 에러
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"Server error: {str(e)}"
                })
    
    except HTTPException as e:
        await websocket.close(code=4001, reason=e.detail)
    except Exception as e:
        await websocket.close(code=4000, reason=f"Server error: {str(e)}")
    finally:
        # 연결 해제 시 매니저에서 제거
        await manager.disconnect(websocket)
        # 데이터베이스 세션 정리
        if db:
            try:
                await db.close()
            except Exception as e:
                print(f"데이터베이스 세션 정리 오류: {e}")
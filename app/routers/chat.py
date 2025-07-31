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
import asyncio
from jose.exceptions import JWTError
from urllib.parse import unquote

router = APIRouter()

def verify_websocket_token(token: str) -> dict:
    """
    WebSocket용 JWT 토큰 검증 함수
    """
    try:
        payload = verify_token(token)
        if payload is None:
            # print(f"❌ 토큰 검증 실패: verify_token이 None 반환")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        # print(f"✅ 토큰 검증 성공: payload={payload}")
        return payload
    except JWTError as e:
        # print(f"❌ JWT 디코딩 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT decode error: {str(e)}"
        )
    except Exception as e:
        # print(f"❌ 토큰 검증 중 예상치 못한 오류: {e}")
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
        # print(f"🔍 WebSocket 토큰 검증 성공: user_id={user_context.get('user_id')}, user_name={user_context.get('user_name')}")
    except Exception as e:
        # print(f"❌ WebSocket 토큰 검증 실패: {e}")
        await websocket.close(code=4001, reason="유효하지 않은 토큰입니다.")
        return
    
    # 데이터베이스 세션 직접 생성
    from app.db.session import AsyncSessionLocal
    db = AsyncSessionLocal()
    
    try:
        # 워크스페이스와 채널 접근 권한 확인
        workspace = await get_workspace_by_name(db, workspace_name)
        # print(f"✅ 워크스페이스 확인 성공: {workspace_name} (ID: {workspace.id})")
        
        channel = await get_channel_by_name(db, channel_name, workspace.id)
        # print(f"✅ 채널 확인 성공: {channel_name} (ID: {channel.id})")
        
        # 워크스페이스 멤버십 확인
        workspace_membership = await get_workspace_membership(db, user_context["user_id"], workspace.id)
        if not workspace_membership:
            # print(f"❌ 워크스페이스 멤버십 없음: user_id={user_context['user_id']}, workspace_id={workspace.id}")
            await websocket.close(code=4003, reason="워크스페이스에 접근할 권한이 없습니다.")
            return
        # print(f"✅ 워크스페이스 멤버십 확인 성공: user_id={user_context['user_id']}")
        
        # 채널 멤버십 확인
        channel_membership = await get_channel_membership(db, user_context["user_id"], channel.id)
        if not channel_membership:
            # print(f"❌ 채널 멤버십 없음: user_id={user_context['user_id']}, channel_id={channel.id}")
            await websocket.close(code=4003, reason="채널에 접근할 권한이 없습니다.")
            return
        # print(f"✅ 채널 멤버십 확인 성공: user_id={user_context['user_id']}")
        
    except Exception as e:
        # print(f"❌ 데이터베이스 오류: {e}")
        await websocket.close(code=4005, reason=f"데이터베이스 오류: {str(e)}")
        return
    
    try:
        # WebSocket 연결 (입장 메시지는 채널 가입 승인 시에만 전송)
        await manager.connect(
            websocket, 
            workspace.id, 
            channel.id, 
            user_context["user_id"], 
            user_context["user_name"],
            False  # WebSocket 연결 시에는 입장 메시지 전송하지 않음
        )
        
        # 연결된 사용자 목록 전송 (기능 비활성화)
        # connected_users = manager.get_connected_users(workspace.id, channel.id)
        # await manager.send_personal_message(websocket, {
        #     "type": "connected_users",
        #     "connected_users": connected_users,
        #     "timestamp": datetime.now().isoformat()
        # })
        
        # 채널의 최신 메시지 50개 히스토리 전송
        try:
            # DynamoDB에서 최신 메시지 50개 조회
            messages = await dynamodb_manager.get_latest_messages(channel.id, limit=50)
            
            if messages:
                # 메시지 히스토리 전송
                await manager.send_personal_message(websocket, {
                    "type": "message_history",
                    "messages": messages,
                    "timestamp": get_current_datetime().isoformat()
                })
                # print(f"✅ 메시지 히스토리 전송 완료: {len(messages)}개 메시지")
            else:
                # print("📭 채널에 메시지가 없습니다.")
                pass
                
        except Exception as e:
            # print(f"❌ 메시지 히스토리 조회 실패: {e}")
            # 히스토리 조회 실패해도 실시간 채팅은 계속 진행
            pass
        
        # 메시지 수신 루프 (시그널 처리를 위한 개선)
        error_count = 0  # 에러 카운터 추가
        max_errors = 10  # 최대 허용 에러 횟수 증가 (더 관대하게)
        
        while True:
            try:
                # 타임아웃 없이 메시지 수신 (실시간 채팅을 위해)
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # 메시지 타입에 따른 처리
                if message_data.get("type") == "message":
                    # 성공적인 메시지 처리 시 에러 카운터 리셋
                    error_count = 0
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
                        # print(f"DynamoDB 메시지 저장 성공: {message_id}")
                    except Exception as e:
                        # print(f"DynamoDB 메시지 저장 실패: {e}")
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
                
                # elif message_data.get("type") == "typing":
                #     # 타이핑 상태 브로드캐스트
                #     await manager.broadcast_to_channel(
                #         workspace.id,
                #         channel.id,
                #         {
                #             "type": "typing",
                #             "user_id": user_context["user_id"],
                #             "user_name": user_context["user_name"],
                #             "timestamp": get_current_datetime().isoformat()
                #         },
                #         exclude_websocket=websocket
                #     )
                
                elif message_data.get("type") == "load_older_messages":
                    # 성공적인 메시지 처리 시 에러 카운터 리셋
                    error_count = 0
                    # 더 이전 메시지 요청 처리
                    try:
                        before_timestamp = message_data.get("before_timestamp")
                        if not before_timestamp:
                            await manager.send_personal_message(websocket, {
                                "type": "error",
                                "message": "이전 메시지 요청에 필요한 timestamp가 없습니다.",
                                "timestamp": get_current_datetime().isoformat()
                            })
                            continue
                        
                        # 더 이전 메시지 조회
                        older_messages = await dynamodb_manager.get_older_messages(
                            channel.id, 
                            before_timestamp, 
                            limit=50
                        )
                        
                        if older_messages:
                            # 이전 메시지 전송
                            await manager.send_personal_message(websocket, {
                                "type": "older_messages",
                                "messages": older_messages,
                                "timestamp": get_current_datetime().isoformat()
                            })
                        else:
                            # 더 이상 이전 메시지가 없음
                            await manager.send_personal_message(websocket, {
                                "type": "no_older_messages",
                                "timestamp": get_current_datetime().isoformat()
                            })
                            
                    except Exception as e:
                        await manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": f"이전 메시지 조회 중 오류가 발생했습니다: {str(e)}",
                            "timestamp": get_current_datetime().isoformat()
                        })
                
                # elif message_data.get("type") == "read_receipt":
                #     # 읽음 확인 처리 (추후 구현)
                #     pass
                    
            except asyncio.CancelledError:
                # 서버 종료 시 WebSocket 연결이 취소됨 (SIGINT 강제종료 포함)
                print(f"🔌 WebSocket 연결 취소됨: {user_context.get('user_name', 'Unknown')}")
                break
            except json.JSONDecodeError:
                # 잘못된 JSON 형식
                error_count += 1
                # print(f"❌ 잘못된 JSON 형식: {user_context.get('user_name', 'Unknown')} (에러 횟수: {error_count})")
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "잘못된 메시지 형식입니다.",
                    "timestamp": get_current_datetime().isoformat()
                })
                
                # 에러 횟수가 최대 허용 횟수를 초과하면 연결 해제
                if error_count >= max_errors:
                    print(f"🚫 최대 에러 횟수 초과로 연결 해제: {user_context.get('user_name', 'Unknown')}")
                    await manager.safe_close_websocket(websocket, code=1007, reason="Too many invalid messages")
                    break
            except Exception as e:
                # 기타 오류 처리
                error_count += 1
                # print(f"❌ 메시지 처리 중 오류: {e} (사용자: {user_context.get('user_name', 'Unknown')}, 에러 횟수: {error_count})")
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"메시지 처리 중 오류가 발생했습니다: {str(e)}",
                    "timestamp": get_current_datetime().isoformat()
                })
                
                # 에러 횟수가 최대 허용 횟수를 초과하거나 심각한 오류인 경우 연결 해제
                if error_count >= max_errors or isinstance(e, (ValueError, TypeError, AttributeError)):
                    print(f"🚫 최대 에러 횟수 초과 또는 심각한 오류로 연결 해제: {user_context.get('user_name', 'Unknown')}")
                    await manager.safe_close_websocket(websocket, code=1011, reason="Internal error")
                    break
                
    except WebSocketDisconnect:
        # WebSocket 연결 해제 처리
        print(f"🔌 WebSocket 연결 해제: {user_context.get('user_name', 'Unknown')}")
        try:
            await manager.safe_disconnect(websocket)
        except Exception as e:
            print(f"❌ WebSocket 연결 해제 중 오류: {e}")
    except asyncio.CancelledError:
        # 서버 종료 시 WebSocket 연결이 취소됨 (SIGINT 강제종료 포함)
        print(f"🔌 WebSocket 연결 취소됨: {user_context.get('user_name', 'Unknown')}")
        try:
            await manager.safe_disconnect(websocket)
        except Exception as e:
            print(f"❌ WebSocket 연결 취소 중 오류: {e}")
    except Exception as e:
        # 기타 예외 처리
        print(f"❌ WebSocket 오류: {e}")
        try:
            # 안전한 웹소켓 닫기
            await manager.safe_close_websocket(websocket, code=1011, reason="Internal error")
        except Exception as close_error:
            print(f"❌ WebSocket 강제 종료 실패: {close_error}")
        finally:
            # 연결 정보 정리
            try:
                await manager.safe_disconnect(websocket)
            except:
                pass
    finally:
        # 데이터베이스 세션 정리
        if db:
            try:
                await db.close()
            except Exception as e:
                print(f"❌ 데이터베이스 세션 정리 오류: {e}")

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import asyncio
from app.core.date_utils import get_current_datetime

class ConnectionManager:
    def __init__(self):
        # {workspace_id: {channel_id: Set[WebSocket]}}
        self.active_connections: Dict[int, Dict[int, Set[WebSocket]]] = {}
        # {WebSocket: (workspace_id, channel_id, user_id, user_name)}
        self.connection_info: Dict[WebSocket, tuple] = {}
    
    async def connect(self, websocket: WebSocket, workspace_id: int, channel_id: int, user_id: int, user_name: str, is_new_member: bool = False):
        await websocket.accept()
        
        # 워크스페이스/채널별 연결 관리
        if workspace_id not in self.active_connections:
            self.active_connections[workspace_id] = {}
        if channel_id not in self.active_connections[workspace_id]:
            self.active_connections[workspace_id][channel_id] = set()
        
        self.active_connections[workspace_id][channel_id].add(websocket)
        self.connection_info[websocket] = (workspace_id, channel_id, user_id, user_name)
        
        # 연결 성공 메시지 전송
        await self.send_personal_message(websocket, {
            "type": "connection",
            "message": "채팅방에 연결되었습니다.",
            "timestamp": get_current_datetime().isoformat()
        })
        
        # 새로 가입한 멤버인 경우에만 다른 사용자들에게 입장 알림
        if is_new_member:
            await self.broadcast_to_channel(
                workspace_id, 
                channel_id, 
                {
                    "type": "user_joined",
                    "user_id": user_id,
                    "user_name": user_name,
                    "message": f"{user_name}님이 채널에 가입하셨습니다.",
                    "timestamp": get_current_datetime().isoformat()
                },
                exclude_websocket=websocket
            )
    
    async def disconnect(self, websocket: WebSocket):
        if websocket in self.connection_info:
            workspace_id, channel_id, user_id, user_name = self.connection_info[websocket]
            
            # 연결 제거
            if workspace_id in self.active_connections and channel_id in self.active_connections[workspace_id]:
                self.active_connections[workspace_id][channel_id].discard(websocket)
                
                # 빈 채널 정리
                if not self.active_connections[workspace_id][channel_id]:
                    del self.active_connections[workspace_id][channel_id]
                if not self.active_connections[workspace_id]:
                    del self.active_connections[workspace_id]
            
            # 연결 정보 제거
            del self.connection_info[websocket]
            
            # 다른 사용자들에게 퇴장 알림
            await self.broadcast_to_channel(
                workspace_id, 
                channel_id, 
                {
                    "type": "user_left",
                    "user_id": user_id,
                    "user_name": user_name,
                    "message": f"{user_name}님이 퇴장하셨습니다.",
                    "timestamp": get_current_datetime().isoformat()
                }
            )
    
    async def shutdown_all_connections(self):
        """서버 종료 시 모든 WebSocket 연결 정리"""
        connections_to_close = list(self.connection_info.keys())
        
        if not connections_to_close:
            print("🔌 종료할 WebSocket 연결이 없습니다.")
            return
        
        print(f"🔌 {len(connections_to_close)}개의 WebSocket 연결 종료 중...")
        
        for websocket in connections_to_close:
            try:
                # 서버 종료 알림 메시지 전송 (타임아웃 추가)
                await asyncio.wait_for(
                    self.send_personal_message(websocket, {
                        "type": "server_shutdown",
                        "message": "서버가 종료됩니다. 잠시 후 다시 연결해주세요.",
                        "timestamp": get_current_datetime().isoformat()
                    }),
                    timeout=1.0
                )
                
                # 정상 종료 코드로 연결 해제 (타임아웃 추가)
                await asyncio.wait_for(
                    websocket.close(code=1000, reason="Server shutdown"),
                    timeout=1.0
                )
                
            except asyncio.TimeoutError:
                # 타임아웃 발생 시 강제 종료
                try:
                    await websocket.close(code=1000, reason="Server shutdown")
                except:
                    pass
            except Exception as e:
                print(f"❌ WebSocket 종료 실패: {e}")
        
        # 연결 정보 초기화
        self.active_connections.clear()
        self.connection_info.clear()
        print("✅ WebSocket 연결 정리 완료")
    
    def get_connection_count(self) -> int:
        """현재 활성 연결 수 반환"""
        return len(self.connection_info)
    
    def get_connection_summary(self) -> dict:
        """연결 상태 요약 반환"""
        total_connections = len(self.connection_info)
        workspace_count = len(self.active_connections)
        channel_count = sum(len(channels) for channels in self.active_connections.values())
        
        return {
            "total_connections": total_connections,
            "workspace_count": workspace_count,
            "channel_count": channel_count,
            "active_workspaces": list(self.active_connections.keys())
        }
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except:
            # 연결이 끊어진 경우
            await self.disconnect(websocket)
    
    async def broadcast_to_channel(self, workspace_id: int, channel_id: int, message: dict, exclude_websocket: WebSocket = None):
        if workspace_id in self.active_connections and channel_id in self.active_connections[workspace_id]:
            disconnected_websockets = set()
            
            for websocket in self.active_connections[workspace_id][channel_id]:
                if websocket != exclude_websocket:
                    try:
                        await websocket.send_text(json.dumps(message, ensure_ascii=False))
                    except:
                        # 연결이 끊어진 웹소켓 수집
                        disconnected_websockets.add(websocket)
            
            # 끊어진 연결들 정리
            for websocket in disconnected_websockets:
                await self.disconnect(websocket)
    
    def get_connected_users(self, workspace_id: int, channel_id: int) -> List[dict]:
        """특정 채널에 연결된 사용자 목록 반환"""
        users = []
        if workspace_id in self.active_connections and channel_id in self.active_connections[workspace_id]:
            for websocket in self.active_connections[workspace_id][channel_id]:
                if websocket in self.connection_info:
                    _, _, user_id, user_name = self.connection_info[websocket]
                    users.append({
                        "user_id": user_id, 
                        "user_name": user_name,
                        "name": user_name,  # 클라이언트 호환성을 위해 추가
                        "avatar": user_name[0] if user_name else "?"
                    })
        return users

# 전역 인스턴스
manager = ConnectionManager() 
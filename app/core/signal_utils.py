import asyncio
import signal
from typing import Optional, Callable
from app.core.websocket_manager import manager

class ServerShutdownManager:
    """서버 종료 관리 클래스"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.shutdown_callback: Optional[Callable] = None
        self._original_sigint_handler = None
        self._original_sigterm_handler = None
    
    def setup_signal_handlers(self, shutdown_callback: Optional[Callable] = None):
        """시그널 핸들러 설정"""
        self.shutdown_callback = shutdown_callback
        
        # 기존 핸들러 백업
        self._original_sigint_handler = signal.getsignal(signal.SIGINT)
        self._original_sigterm_handler = signal.getsignal(signal.SIGTERM)
        
        # 새로운 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러: 서버 종료 시그널 처리"""
        self.shutdown_event.set()
        
        if self.shutdown_callback:
            try:
                self.shutdown_callback()
            except Exception as e:
                print(f"종료 콜백 실행 중 오류: {e}")
    
    def restore_signal_handlers(self):
        """원본 시그널 핸들러 복원"""
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        if self._original_sigterm_handler:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
    
    async def shutdown_websockets(self):
        """모든 WebSocket 연결 정상 종료"""
        await manager.shutdown_all_connections()
    
    async def graceful_shutdown(self):
        """우아한 서버 종료 프로세스"""
        await self.shutdown_websockets()
        await self._cleanup_database()
        self.restore_signal_handlers()
    
    async def _cleanup_database(self):
        """데이터베이스 연결 정리"""
        try:
            # 데이터베이스 연결 정리 코드 추가 가능
            pass
        except Exception as e:
            print(f"데이터베이스 정리 중 오류: {e}")
    
    def is_shutdown_requested(self) -> bool:
        """종료 요청 여부 확인"""
        return self.shutdown_event.is_set()

# 전역 인스턴스
shutdown_manager = ServerShutdownManager()

def create_shutdown_handler():
    """FastAPI 종료 핸들러 생성"""
    async def shutdown_handler():
        await shutdown_manager.graceful_shutdown()
    return shutdown_handler

def setup_server_shutdown():
    """서버 종료 설정"""
    shutdown_manager.setup_signal_handlers()
    return shutdown_manager

def handle_keyboard_interrupt():
    """키보드 인터럽트 처리"""
    asyncio.run(shutdown_manager.shutdown_websockets())

def handle_server_error(error: Exception):
    """서버 오류 처리"""
    asyncio.run(shutdown_manager.shutdown_websockets()) 
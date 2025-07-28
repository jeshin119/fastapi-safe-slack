import asyncio
import signal
import os
from typing import Optional, Callable
from app.core.websocket_manager import manager

class ServerShutdownManager:
    """서버 종료 관리 클래스"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.shutdown_callback: Optional[Callable] = None
        self._original_sigint_handler = None
        self._force_exit_handler = None
    
    def setup_signal_handlers(self, shutdown_callback: Optional[Callable] = None):
        """시그널 핸들러 설정"""
        self.shutdown_callback = shutdown_callback
        
        # 기존 핸들러 백업
        self._original_sigint_handler = signal.getsignal(signal.SIGINT)
        
        # 강제 종료 핸들러
        def force_exit_handler(signum, frame):
            print(f"\n🛑 강제 종료 시그널 수신: {signum}")
            try:
                # WebSocket 연결 정리 시도
                asyncio.create_task(self.shutdown_websockets())
            except:
                pass
            # 즉시 종료
            os._exit(0)
        
        self._force_exit_handler = force_exit_handler
        
        # 새로운 핸들러 등록 (SIGINT만)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러: 서버 종료 시그널 처리"""
        print(f"\n🛑 종료 시그널 수신: {signum}")
        self.shutdown_event.set()
        
        if self.shutdown_callback:
            try:
                self.shutdown_callback()
            except Exception as e:
                print(f"종료 콜백 실행 중 오류: {e}")
        
        # 강제 종료 핸들러도 등록 (SIGINT만)
        if self._force_exit_handler:
            signal.signal(signal.SIGINT, self._force_exit_handler)
    
    def restore_signal_handlers(self):
        """원본 시그널 핸들러 복원"""
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
    
    async def shutdown_websockets(self):
        """모든 WebSocket 연결 정상 종료"""
        print("🔌 WebSocket 연결 정리 중...")
        try:
            await manager.shutdown_all_connections()
            print("✅ WebSocket 연결 정리 완료")
        except Exception as e:
            print(f"❌ WebSocket 연결 정리 중 오류: {e}")
    
    async def graceful_shutdown(self):
        """우아한 서버 종료 프로세스"""
        print("🔄 서버 종료 프로세스 시작...")
        await self.shutdown_websockets()
        await self._cleanup_database()
        self.restore_signal_handlers()
        print("✅ 서버 종료 완료")
    
    async def _cleanup_database(self):
        """데이터베이스 연결 정리"""
        try:
            print("🗄️ 데이터베이스 연결 정리 중...")
            # 데이터베이스 연결 정리 코드 추가 가능
            # asyncio 이벤트 루프가 닫히기 전에 정리 완료
        except Exception as e:
            print(f"❌ 데이터베이스 정리 중 오류: {e}")
    
    def is_shutdown_requested(self) -> bool:
        """종료 요청 여부 확인"""
        return self.shutdown_event.is_set()

# 전역 인스턴스
shutdown_manager = ServerShutdownManager()

def create_shutdown_handler():
    """FastAPI 종료 핸들러 생성"""
    async def shutdown_handler():
        try:
            await shutdown_manager.graceful_shutdown()
        except Exception as e:
            print(f"❌ 종료 핸들러 실행 중 오류: {e}")
    return shutdown_handler

def setup_server_shutdown():
    """서버 종료 설정"""
    shutdown_manager.setup_signal_handlers()
    return shutdown_manager

def handle_keyboard_interrupt():
    """키보드 인터럽트 처리"""
    print("🛑 키보드 인터럽트 처리 중...")
    try:
        # 새로운 이벤트 루프 생성하여 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(shutdown_manager.shutdown_websockets())
        loop.close()
    except Exception as e:
        print(f"❌ 키보드 인터럽트 처리 중 오류: {e}")

def handle_server_error(error: Exception):
    """서버 오류 처리"""
    print(f"❌ 서버 오류 처리 중: {error}")
    try:
        # 새로운 이벤트 루프 생성하여 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(shutdown_manager.shutdown_websockets())
        loop.close()
    except Exception as e:
        print(f"❌ 서버 오류 처리 중 오류: {e}") 
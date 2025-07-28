import uvicorn
from app.main import app
from app.core.signal_utils import (
    setup_server_shutdown,
    create_shutdown_handler,
    handle_keyboard_interrupt,
    handle_server_error
)
import signal
import os

if __name__ == "__main__":
    # 서버 종료 설정
    setup_server_shutdown()
    
    # FastAPI 종료 핸들러 등록
    app.add_event_handler("shutdown", create_shutdown_handler())
    
    # 강제 종료를 위한 시그널 핸들러 추가
    def force_exit(signum, frame):
        print(f"\n🛑 강제 종료 요청됨 (시그널: {signum})...")
        # 즉시 종료 (타임아웃 없이)
        os._exit(0)
    
    # SIGINT (Ctrl+C) 강제 종료 핸들러 등록
    signal.signal(signal.SIGINT, force_exit)
    
    # 환경 변수 설정으로 uvicorn의 시그널 처리 개선
    os.environ["UVICORN_LOOP"] = "asyncio"
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",        # 이건 나중에 호스트 변경해야함 🐰
            port=8000,
            reload=True,            # 출시할 때는 False로 변경해야함 🐰
            log_level="info",     # info → warning 변경  
            server_header=True,
            use_colors=True,         # 로그 색상 활성화 (개발용)
            proxy_headers=True,      # 프록시 환경 대응
            # WebSocket 연결 시 Ctrl+C 처리를 위한 설정
            loop="asyncio",          # asyncio 이벤트 루프 명시적 사용
            access_log=True,         # 접근 로그 활성화
            # 추가 설정
            timeout_keep_alive=30,   # keep-alive 타임아웃
            timeout_graceful_shutdown=5,  # 우아한 종료 타임아웃 (매우 짧게)
        )
    except KeyboardInterrupt:
        print("\n🛑 키보드 인터럽트 감지됨")
        handle_keyboard_interrupt()
    except Exception as e:
        print(f"\n❌ 서버 오류: {e}")
        handle_server_error(e)

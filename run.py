import uvicorn
from app.main import app
from app.core.signal_utils import (
    setup_server_shutdown,
    create_shutdown_handler,
    handle_keyboard_interrupt,
    handle_server_error
)

if __name__ == "__main__":
    # 서버 종료 설정
    setup_server_shutdown()
    
    # FastAPI 종료 핸들러 등록
    app.add_event_handler("shutdown", create_shutdown_handler())
    
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
        )
    except KeyboardInterrupt:
        handle_keyboard_interrupt()
    except Exception as e:
        handle_server_error(e)

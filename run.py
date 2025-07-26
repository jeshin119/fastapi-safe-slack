import uvicorn
from app.main import app

if __name__ == "__main__":
    # 최소 보안 개선 버전
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",        # 이건 나중에 호스트 변경해야함 🐰
        port=8000,
        reload=True,            # 출시할 때는 False로 변경해야함 🐰
        log_level="info",     # info → warning 변경  
        server_header=False,
        use_colors=True,         # 로그 색상 활성화 (개발용)
        proxy_headers=True,      # 프록시 환경 대응
    )

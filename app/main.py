from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import auth, workspaces, channels, files, chat
import os
from pathlib import Path

app = FastAPI(
    title="Safe Slack API",
    description="워크스페이스 기반 협업 플랫폼 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent  # app/
app.mount("/static", StaticFiles(directory=BASE_DIR / "front", html=True), name="static")

# 라우터 등록
app.include_router(auth.router, prefix="/auth", tags=["인증"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["워크스페이스"])
app.include_router(channels.router, prefix="/channels", tags=["채널"])

app.include_router(files.router, prefix="/channels", tags=["파일"])
app.include_router(chat.router, tags=["채팅"])

@app.get("/")
async def serve_root():
    return FileResponse(BASE_DIR / "front" / "index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/test-chat")
async def test_chat():
    """채팅 테스트 페이지 제공"""
    return FileResponse(BASE_DIR / "front" / "pages" / "workspace"/"chat2.html")

@app.get("/test-websocket")
async def test_websocket():
    """WebSocket 테스트 페이지 제공"""
    return FileResponse(BASE_DIR / "front" / "test-websocket.html")

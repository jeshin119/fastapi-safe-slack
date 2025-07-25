from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import auth, workspaces, channels, files, chat
import os

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

# 정적 파일 제공 설정
app.mount("/front", StaticFiles(directory="app/front"), name="static")

# 라우터 등록
app.include_router(auth.router, prefix="/auth", tags=["인증"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["워크스페이스"])
app.include_router(channels.router, prefix="/channels", tags=["채널"])

app.include_router(files.router, prefix="/channels", tags=["파일"])
app.include_router(chat.router, tags=["채팅"])

@app.get("/")
async def root():
    """루트 경로에서 index.html 제공"""
    return FileResponse("app/front/index.html")

#워크스페이스 테스트 페이지들
@app.get("/workspace/chat.html")
async def workspace_chat():
    """워크스페이스 채팅 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/chat.html")

@app.get("/workspace/channel-add.html")
async def workspace_channel_add():
    """워크스페이스 채널 추가 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/channel-add.html")

@app.get("/workspace/file.html")
async def workspace_file():
    """워크스페이스 파일 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/file.html")

@app.get("/workspace/workspace-files.html")
async def workspace_files():
    """워크스페이스 파일 목록 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/workspace-files.html")

@app.get("/workspace/workspace-main.html")
async def workspace_main():
    """워크스페이스 메인 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/workspace-main.html")

@app.get("/workspace/workspace-select.html")
async def workspace_select():
    """워크스페이스 선택 테스트 페이지 제공"""
    return FileResponse("app/front/pages/workspace/workspace-select.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

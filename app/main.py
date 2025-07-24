from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, workspaces, channels, messages, files, chat

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

# 라우터 등록
app.include_router(auth.router, prefix="/auth", tags=["인증"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["워크스페이스"])
app.include_router(channels.router, prefix="/channels", tags=["채널"])
app.include_router(messages.router, prefix="/channels", tags=["메시지"])
app.include_router(files.router, prefix="/channels", tags=["파일"])
app.include_router(chat.router, tags=["채팅"])

@app.get("/")
async def root():
    return {"message": "Safe Slack API에 오신 것을 환영합니다!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 
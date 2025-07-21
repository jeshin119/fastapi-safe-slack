from fastapi import APIRouter
from app.api.endpoints import user, workspace, channel, message, file

api_router = APIRouter()

api_router.include_router(user.router, prefix="/auth", tags=["인증"])
api_router.include_router(workspace.router, prefix="/workspaces", tags=["워크스페이스"])
api_router.include_router(channel.router, prefix="/channels", tags=["채널"])
api_router.include_router(message.router, prefix="/channels", tags=["메시지"])
api_router.include_router(file.router, prefix="/channels", tags=["파일"]) 
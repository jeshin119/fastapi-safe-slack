from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import api_router

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
app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Safe Slack API에 오신 것을 환영합니다!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 
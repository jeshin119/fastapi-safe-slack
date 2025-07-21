# 기존 app/routers/channels.py의 내용을 이 파일로 이동
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, Channel, ChannelMember, WorkspaceMember
from app.schemas.schemas import ChannelCreate, ChannelResponse, ChannelJoinRequestResponse
from app.core.utils import get_current_user, check_user_permission
from datetime import datetime

router = APIRouter()

# 이하 기존 channels.py의 라우터 함수들 복사 (import 경로만 새 구조에 맞게 수정)
# ... (생략, 실제 코드 이동 필요) 
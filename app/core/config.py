from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # DB 접속 정보 (비동기, .env에서 읽음)
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    
    # JWT 설정 (.env에서 읽음)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"  # 알고리즘은 코드에 고정
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # AWS S3 설정 (.env에서 읽음)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    
    # 이메일 설정 (.env에서 읽음)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings() 
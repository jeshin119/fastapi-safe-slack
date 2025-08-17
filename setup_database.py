#!/usr/bin/env python3
"""
Safe Slack Database Setup Script
이 스크립트를 실행하여 데이터베이스와 테이블을 자동으로 생성하세요.

사용법:
    python setup_database.py

필수사항:
    - MySQL이 설치되어 있어야 함
    - .env 파일에 데이터베이스 설정이 되어 있어야 함
    - MySQL 서버에 접근 권한이 있어야 함
"""

import asyncio
import sys
from sqlalchemy import text, create_engine
from app.db.session import engine
from app.core.config import settings

# SQL 테이블 생성 스크립트들
TABLE_CREATION_SCRIPTS = [
    # 1. 사용자 테이블
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50),
        email VARCHAR(100) NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        profile_image VARCHAR(255),
        is_email_verified BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # 2. 직급 테이블
    """
    CREATE TABLE IF NOT EXISTS roles (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        level INT NOT NULL
    )
    """,
    
    # 3. 워크스페이스 테이블
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # 4. 워크스페이스 멤버십 테이블
    """
    CREATE TABLE IF NOT EXISTS workspace_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        workspace_id INT NOT NULL,
        role_id INT NOT NULL,
        is_workspace_admin BOOLEAN DEFAULT FALSE,
        is_contractor BOOLEAN DEFAULT FALSE,
        start_date DATE,
        end_date DATE,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )
    """,
    
    # 5. 초대 코드 테이블
    """
    CREATE TABLE IF NOT EXISTS invite_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(32) NOT NULL UNIQUE,
        workspace_id INT NOT NULL,
        expires_at DATETIME,
        used BOOLEAN DEFAULT FALSE,
        created_by INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        used_at DATETIME,
        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """,
    
    # 6. 워크스페이스 가입 요청 테이블
    """
    CREATE TABLE IF NOT EXISTS workspace_join_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        invite_code_id INT NOT NULL,
        role_id INT NOT NULL,
        status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (invite_code_id) REFERENCES invite_codes(id),
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )
    """,
    
    # 7. 채널 테이블
    """
    CREATE TABLE IF NOT EXISTS channels (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        workspace_id INT NOT NULL,
        created_by INT,
        is_default BOOLEAN DEFAULT FALSE,
        is_public BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """,
    
    # 8. 채널 멤버십 테이블
    """
    CREATE TABLE IF NOT EXISTS channel_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        channel_id INT NOT NULL,
        status ENUM('pending', 'approved', 'rejected') DEFAULT 'approved',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (channel_id) REFERENCES channels(id)
    )
    """,
    
    # 9. 메시지 테이블
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        channel_id INT NOT NULL,
        user_id INT NOT NULL,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (channel_id) REFERENCES channels(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    
    # 10. 파일 테이블
    """
    CREATE TABLE IF NOT EXISTS files (
        id INT AUTO_INCREMENT PRIMARY KEY,
        uploaded_by INT NOT NULL,
        channel_id INT NOT NULL,
        filename VARCHAR(255),
        s3_url TEXT,
        min_role_id INT,
        valid_from DATE,
        valid_to DATE,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (uploaded_by) REFERENCES users(id),
        FOREIGN KEY (channel_id) REFERENCES channels(id),
        FOREIGN KEY (min_role_id) REFERENCES roles(id)
    )
    """
]

# 기본 데이터 삽입 스크립트들
DATA_INSERTION_SCRIPTS = [
    # 기본 직급 데이터 삽입
    """
    INSERT IGNORE INTO roles (name, level) VALUES
    ('사원', 1),
    ('대리', 2),
    ('과장', 3),
    ('팀장', 4),
    ('부장', 5),
    ('이사', 6)
    """
]

async def create_tables():
    """데이터베이스 테이블을 생성합니다."""
    try:
        print("🔄 데이터베이스 연결 중...")
        print(f"📍 데이터베이스: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
        
        async with engine.begin() as conn:
            print("✅ 데이터베이스 연결 성공!")
            print("\n🔨 테이블 생성 중...")
            
            # 테이블 생성
            for i, script in enumerate(TABLE_CREATION_SCRIPTS, 1):
                table_name = script.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
                print(f"  [{i:2d}/10] {table_name} 테이블 생성...")
                await conn.execute(text(script))
            
            print("\n📊 기본 데이터 삽입 중...")
            
            # 기본 데이터 삽입
            for script in DATA_INSERTION_SCRIPTS:
                await conn.execute(text(script))
            
            print("  ✅ 기본 직급 데이터 삽입 완료")
            
        print("\n🎉 데이터베이스 설정이 완료되었습니다!")
        print("\n📋 생성된 테이블:")
        print("  - users (사용자)")
        print("  - roles (직급)")
        print("  - workspaces (워크스페이스)")
        print("  - workspace_members (워크스페이스 멤버)")
        print("  - invite_codes (초대코드)")
        print("  - workspace_join_requests (워크스페이스 가입요청)")
        print("  - channels (채널)")
        print("  - channel_members (채널 멤버)")
        print("  - messages (메시지)")
        print("  - files (파일)")
        print("\n🚀 이제 서버를 실행할 수 있습니다: python run.py")
        
    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")
        print("\n🔍 문제 해결 방법:")
        print("  1. MySQL이 실행 중인지 확인하세요")
        print("  2. .env 파일의 데이터베이스 설정을 확인하세요")
        print("  3. 데이터베이스가 생성되어 있는지 확인하세요:")
        print("     mysql -u root -p -e \"CREATE DATABASE safe_slack CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\"")
        sys.exit(1)

def create_database_if_not_exists():
    """데이터베이스가 없으면 생성합니다."""
    try:
        # 데이터베이스명을 제외한 연결 문자열 생성
        base_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}"
        base_engine = create_engine(base_url)
        
        with base_engine.connect() as conn:
            # 데이터베이스 존재 여부 확인
            result = conn.execute(text(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{settings.DB_NAME}'"))
            if not result.fetchone():
                print(f"📦 데이터베이스 '{settings.DB_NAME}' 생성 중...")
                conn.execute(text(f"CREATE DATABASE {settings.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                print(f"✅ 데이터베이스 '{settings.DB_NAME}' 생성 완료!")
            else:
                print(f"✅ 데이터베이스 '{settings.DB_NAME}' 이미 존재합니다.")
        
        base_engine.dispose()
        return True
    except Exception as e:
        print(f"❌ 데이터베이스 생성 중 오류: {e}")
        return False

async def check_database_exists():
    """데이터베이스 존재 여부를 확인합니다."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            return True
    except Exception:
        return False

async def main():
    """메인 함수"""
    print("🗄️  Safe Slack 데이터베이스 설정")
    print("=" * 50)
    
    # 환경변수 확인
    if not all([settings.DB_USER, settings.DB_PASSWORD, settings.DB_HOST, settings.DB_NAME]):
        print("❌ .env 파일의 데이터베이스 설정이 누락되었습니다.")
        print("필요한 환경변수: DB_USER, DB_PASSWORD, DB_HOST, DB_NAME")
        sys.exit(1)
    
    # 데이터베이스 생성 (없으면)
    if not create_database_if_not_exists():
        print(f"❌ 데이터베이스 '{settings.DB_NAME}' 생성에 실패했습니다.")
        print("\nMySQL 서버가 실행 중인지 확인하세요.")
        sys.exit(1)
    
    # 데이터베이스 연결 확인
    if not await check_database_exists():
        print(f"❌ 데이터베이스 '{settings.DB_NAME}'에 연결할 수 없습니다.")
        print("\nMySQL 서버 연결을 확인하세요.")
        sys.exit(1)
    
    # 테이블 생성
    await create_tables()

if __name__ == "__main__":
    asyncio.run(main())

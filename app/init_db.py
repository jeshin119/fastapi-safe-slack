import asyncio
from app.db.session import engine
from sqlalchemy import text

async def init_db():
    async with engine.begin() as conn:
        # 1. 사용자 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50),
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                profile_image VARCHAR(255),
                is_email_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 2. 직급 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                level INT NOT NULL
            )
        """))
        
        # 3. 워크스페이스 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 4. 워크스페이스 멤버십 테이블
        await conn.execute(text("""
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
        """))
        
        # 5. 초대코드 테이블
        await conn.execute(text("""
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
        """))
        
        # 6. 워크스페이스 가입 요청 테이블
        await conn.execute(text("""
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
        """))
        
        # 7. 채널 테이블
        await conn.execute(text("""
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
        """))
        
        # 8. 채널 멤버십 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS channel_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                channel_id INT NOT NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'approved',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            )
        """))
        
        # 9. 메시지 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                channel_id INT NOT NULL,
                user_id INT NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        
        # 10. 파일 테이블
        await conn.execute(text("""
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
        """))
        
        print("모든 테이블이 생성되었습니다.")
        
        # 직급 더미데이터 추가
        await conn.execute(text("""
            INSERT IGNORE INTO roles (name, level) VALUES
            ('사원', 1),
            ('대리', 2),
            ('과장', 3),
            ('팀장', 4),
            ('부장', 5),
            ('이사', 6)
        """))
        
        print("직급 더미데이터가 추가되었습니다.")

if __name__ == "__main__":
    asyncio.run(init_db()) 
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.models import Role
from app.core.config import settings

def init_db():
    """데이터베이스 초기화 및 기본 데이터 삽입"""
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 기본 직급 데이터 삽입
        roles = [
            {"name": "사원", "level": 1},
            {"name": "대리", "level": 2},
            {"name": "과장", "level": 3},
            {"name": "팀장", "level": 4},
            {"name": "부장", "level": 5},
            {"name": "이사", "level": 6}
        ]
        
        for role_data in roles:
            existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing_role:
                role = Role(**role_data)
                db.add(role)
        
        db.commit()
        print("데이터베이스 초기화가 완료되었습니다.")
        
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db() 
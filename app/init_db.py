import asyncio
from app.db.session import engine
from app.models.models import Base, Role
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 기본 Role 데이터 추가
    async with AsyncSession(engine) as session:
        # 기존 Role 데이터 확인
        result = await session.execute(select(Role))
        existing_roles = result.scalars().all()
        
        if not existing_roles:
            # 기본 Role 데이터 추가
            default_roles = [
                Role(name="사원", level=1),
                Role(name="대리", level=2),
                Role(name="과장", level=3),
                Role(name="부장", level=4),
                Role(name="이사", level=5),
                Role(name="대표", level=6)
            ]
            
            for role in default_roles:
                session.add(role)
            
            await session.commit()
            print("기본 Role 데이터가 추가되었습니다.")
        else:
            print("Role 데이터가 이미 존재합니다.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db()) 
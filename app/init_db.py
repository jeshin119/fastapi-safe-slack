import asyncio
from app.db.session import engine, Base

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("데이터베이스 테이블 생성 완료.")

if __name__ == "__main__":
    asyncio.run(create_tables()) 
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession  # type: ignore[attr-defined]
from sqlmodel import SQLModel
try:
    from config import settings
except ImportError:
    from ..config import settings

# Create a database engine to connect with database
engine = create_async_engine(
    # database type/dialect and file name
    url=settings.POSTGRES_URL,
    # Log sql queries
    echo=True,
)

# Create async session factory using SQLModel's AsyncSession
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_tables():
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


async def get_session():
    async with async_session_maker() as session:
        yield session


SessionDep=Annotated[AsyncSession,Depends(get_session)]
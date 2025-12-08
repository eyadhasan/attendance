from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession  # type: ignore[attr-defined]
from sqlmodel import SQLModel
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from config import settings
except ImportError:
    from ..config import settings

# Create a database engine to connect with database
# Handle SSL for cloud deployments (like Railway/Heroku)
import ssl

connect_args = {}
# Check if we are in a production-like environment (not localhost)
# We apply this fix regardless of whether 'ssl' is in the URL, because we need to DISABLE hostname checking
if settings.POSTGRES_URL and "localhost" not in settings.POSTGRES_URL and "127.0.0.1" not in settings.POSTGRES_URL:
    try:
        # Create a custom SSL context that disables hostname verification
        # This fixes 'TargetServerAttributeNotMatched' errors on Railway/Render
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context
        logger.info("Applied custom SSL context for database connection (Cloud environment detected)")
    except Exception as e:
        logger.error(f"Failed to create SSL context: {e}")

engine = create_async_engine(
    # database type/dialect and file name
    url=settings.POSTGRES_URL,
    # Log sql queries
    echo=True,
    pool_pre_ping=True, # Verify connection before usage
    connect_args=connect_args,
)

# Create async session factory using SQLModel's AsyncSession
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_tables():
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to create database tables (Attempt {attempt + 1}/{max_retries})...")
            async with engine.begin() as connection:
                await connection.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables created successfully!")
            return
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Could not connect to database.")
                raise e


async def get_session():
    async with async_session_maker() as session:
        yield session


SessionDep=Annotated[AsyncSession,Depends(get_session)]
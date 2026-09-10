"""Database setup and session management using SQLAlchemy AsyncIO."""

import logging
from pathlib import Path

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from src.shared.settings import DatabaseType, settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Create database engine based on DB_TYPE
if settings.DB_TYPE == DatabaseType.SQLITE:
    # Ensure the directory for SQLite database exists
    db_path = Path(settings.SQLITE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create SQLite engine
    engine = create_async_engine(
        settings.DB_URI,
        echo=settings.DEBUG,
        future=True,
        connect_args={"check_same_thread": False},  # Required for SQLite with async
    )
    logger.info(f"Using SQLite database at: {settings.SQLITE_PATH}")
else:
    # Create PostgreSQL engine with connection pooling
    engine = create_async_engine(
        settings.DB_URI,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
    logger.info(f"Using PostgreSQL database at: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DB}")

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


async def create_default_admin():
    """Create default admin user if no admin exists"""
    from src.shared.database.models import UserDB

    async with AsyncSessionLocal() as session:
        # Check if any admin user exists
        result = await session.execute(select(UserDB).where(UserDB.role == "admin"))
        admin_exists = result.scalar_one_or_none()

        if not admin_exists:
            logger.info("No admin user found, creating default admin")
            admin_user = UserDB(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Default admin user created with email: {settings.ADMIN_EMAIL}")
        else:
            logger.info("Admin user already exists, skipping creation")


async def init_db():
    """Initialize the database (create tables and default admin)"""
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database schema initialized")

    # Create default admin user
    await create_default_admin()

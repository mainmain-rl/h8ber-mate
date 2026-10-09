"""Shared database module.

Public API:
- get_db, init_db: Database session management
- engine, Base, AsyncSessionLocal: SQLAlchemy internals
- UserDB, UserNamespaceDB, ApiKeyDB, RefreshTokenDB: Shared models
- get_current_time, hash_password, verify_password: Utilities
"""

from .database import AsyncSessionLocal, Base, engine, get_db, init_db, hash_password, verify_password
from .models import ApiKeyDB, RefreshTokenDB, UserDB, UserNamespaceDB, get_current_time

__all__ = [
    "get_db",
    "init_db",
    "engine",
    "Base",
    "AsyncSessionLocal",
    "UserDB",
    "UserNamespaceDB",
    "ApiKeyDB",
    "RefreshTokenDB",
    "get_current_time",
    "hash_password",
    "verify_password",
]
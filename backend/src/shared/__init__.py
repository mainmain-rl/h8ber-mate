"""Shared kernel module - core utilities used by all modules.

Public API:
- Database: get_db, init_db, engine, Base, AsyncSessionLocal, UserDB, UserNamespaceDB, ApiKeyDB, RefreshTokenDB, get_current_time
- Settings: settings
- Auth: get_current_user, get_current_admin_user, check_namespace_access, filter_namespaces_by_access, create_access_token, verify_token
- Audit: get_client_ip, log_action
"""

from .database import (
    AsyncSessionLocal,
    Base,
    engine,
    get_db,
    init_db,
    UserDB,
    UserNamespaceDB,
    ApiKeyDB,
    RefreshTokenDB,
    get_current_time,
    hash_password,
    verify_password,
)
from .settings import settings
from .auth.auth_simple import (
    get_current_user,
    get_current_admin_user,
    check_namespace_access,
    filter_namespaces_by_access,
    create_access_token,
    verify_token,
)
from .auth import auth_router
from .audit import get_client_ip, log_action

__all__ = [
    # Database
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
    # Settings
    "settings",
    # Auth
    "get_current_user",
    "get_current_admin_user",
    "check_namespace_access",
    "filter_namespaces_by_access",
    "create_access_token",
    "verify_token",
    "auth_router",
    # Audit
    "get_client_ip",
    "log_action",
]
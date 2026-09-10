"""
h8ber-mate - Simplified all-in-one version
FastAPI backend serving React frontend static files
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.router import router
from src.schedules.services import get_scheduler
from src.shared.database import init_db
from src.shared.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.stop()
    logger.info("Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="h8ber-mate",
    description="Kubernetes deployment hibernation scheduler - All-in-one",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure rate limiter for the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include API routes
app.include_router(router, prefix="/api")

# Serve static files (React build)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    logger.info(f"Serving static files from {static_dir}")
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React app for all non-API routes"""
        # If path starts with api/, let FastAPI handle it
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        # Check if file exists in static dir
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise, serve index.html (React Router will handle routing)
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return {"error": "Frontend not built. Run 'npm run build' in frontend/"}
else:
    logger.warning(f"Static directory not found at {static_dir}")
    logger.warning("Frontend will not be served. Build frontend first: cd frontend && npm run build")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path
import time

from .core.config import settings
from .db.database import init_db
from .api.api_v1.api import api_router
from .middleware.tenant_middleware import TenantMiddleware

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="A comprehensive project management SaaS platform",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.zphere.app"]
    )

# Add tenant middleware for multi-tenant routing
app.add_middleware(TenantMiddleware)


# Middleware for request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error": str(exc),
                "traceback": traceback.format_exc()
            }
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Determine frontend build directory
FRONTEND_BUILD_DIR = (Path(__file__).resolve().parents[2] / "frontend" / "build")

# Root endpoint
@app.get("/")
async def root():
    if FRONTEND_BUILD_DIR.exists():
        index_path = FRONTEND_BUILD_DIR / "index.html"
        return FileResponse(index_path)
    return RedirectResponse(url="/api/v1/docs")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2025-08-22T22:00:00Z"}

# Mount uploads directory for serving uploaded assets (e.g., logos)
try:
    from .core.config import settings as _settings
    uploads_dir = Path(_settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
except Exception:
    # Best-effort; do not crash if mount fails
    pass

# Serve frontend build (single-port setup)
if FRONTEND_BUILD_DIR.exists():
    # Serve static assets under /static (CRA output)
    static_dir = FRONTEND_BUILD_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # SPA fallback: serve index.html for any non-API path
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # If request starts with /api, let API/router handle it
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        index_path = FRONTEND_BUILD_DIR / "index.html"
        return FileResponse(index_path)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks"""
    if settings.ENVIRONMENT == "development":
        from .db.database import init_db
        await init_db()
    # Ensure platform admin exists (best-effort)
    try:
        from .services.bootstrap_service import ensure_platform_admin
        await ensure_platform_admin()
    except Exception:
        pass

    # Ensure Stripe prices exist (best-effort)
    try:
        from .services.stripe_bootstrap_service import ensure_stripe_prices
        ensure_stripe_prices()
    except Exception:
        pass

    # Start background scheduler (best-effort)
    try:
        # Run scheduler loop in the background
        import asyncio
        from .services.scheduler import scheduler_loop
        asyncio.create_task(scheduler_loop())
    except Exception:
        pass

    # Ensure task columns exist across tenant DBs (best-effort)
    try:
        from .services.schema_ensure_service import ensure_task_columns
        await ensure_task_columns()
    except Exception:
        pass


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup tasks on shutdown"""
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )

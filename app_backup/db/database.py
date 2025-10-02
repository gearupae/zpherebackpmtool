from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from ..core.config import settings

# Master database base for organizations and users
Base = declarative_base()

# Legacy compatibility - these will be deprecated
# Async engine for master database operations
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=30,
    )

# Legacy session maker (for master database)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Master database session dependency
async def get_master_db() -> AsyncSession:
    """Dependency to get master database session"""
    from .tenant_manager import tenant_manager
    session = await tenant_manager.get_master_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

# Legacy compatibility
async def get_db() -> AsyncSession:
    """Legacy dependency - use get_master_db or get_tenant_db instead"""
    async for session in get_master_db():
        yield session

# Tenant database session dependency (requires organization context)
async def get_tenant_db(organization_id: str) -> AsyncSession:
    """Dependency to get tenant database session"""
    from .tenant_manager import tenant_manager
    session = await tenant_manager.get_tenant_session(organization_id)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_master_db():
    """Initialize master database tables (organizations and users only)"""
    from .tenant_manager import tenant_manager
    async with tenant_manager.master_engine.begin() as conn:
        # Import master models only
        from ..models.master import user, organization
        await conn.run_sync(Base.metadata.create_all)

async def init_tenant_db(organization_id: str):
    """Initialize tenant database tables"""
    from .tenant_manager import tenant_manager, TenantBase
    engine = tenant_manager._get_tenant_engine(organization_id)
    async with engine.begin() as conn:
        # Import tenant models (excluding user and organization)
        from ..models.tenant import project, customer
        # Import tenant base
        await conn.run_sync(TenantBase.metadata.create_all)

# Legacy compatibility
async def init_db():
    """Legacy init - use init_master_db instead"""
    await init_master_db()

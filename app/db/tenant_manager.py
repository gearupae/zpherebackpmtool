"""
Multi-tenant database manager for separate database per organization
"""
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
# Only import asyncpg if not using SQLite
try:
    import asyncpg
    HAS_POSTGRESQL = True
except ImportError:
    HAS_POSTGRESQL = False
from ..core.config import settings
from .database import Base

class TenantDatabaseManager:
    """Manages separate databases for each organization/tenant"""
    
    def __init__(self):
        self._engines: Dict[str, any] = {}
        self._session_makers: Dict[str, any] = {}
        
        # Master database connection for organizations and users
        self.master_engine = self._create_master_engine()
        self.master_session_maker = async_sessionmaker(
            self.master_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    def _create_master_engine(self):
        """Create master database engine"""
        if settings.DATABASE_URL.startswith("sqlite"):
            return create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
            )
        else:
            return create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
    
    def _get_tenant_database_url(self, organization_id: str) -> str:
        """Generate database URL for a specific tenant"""
        if settings.DATABASE_URL.startswith("sqlite"):
            return f"sqlite+aiosqlite:///./tenant_{organization_id}.db"
        else:
            # For PostgreSQL, create a separate database per tenant
            base_url = settings.DATABASE_URL.rsplit('/', 1)[0]  # Remove database name
            return f"{base_url}/zphere_tenant_{organization_id}"
    
    async def create_tenant_database(self, organization_id: str) -> bool:
        """Create a new database for a tenant"""
        try:
            if settings.DATABASE_URL.startswith("sqlite"):
                # SQLite: Database is created automatically when first accessed
                engine = self._get_tenant_engine(organization_id)
                async with engine.begin() as conn:
                    # Import all models to ensure they are registered with Base before create_all
                    from ..models import (
                        user, organization, project, task, customer, project_invoice,
                        project_comment, item, context_card, handoff_summary, decision_log,
                        knowledge_base, workspace, milestone, recurring_task, task_assignee, subscription, proposal, project_report_schedule
                    )
                    from ..models import focus
                    from ..models import goal
                    from ..models import ai
                    from ..models import chat
                    from ..models.tenant import todo
                    # Create all tables for tenant using the shared model metadata
                    await conn.run_sync(Base.metadata.create_all)
                return True
            else:
                # PostgreSQL: Create database manually
                if not HAS_POSTGRESQL:
                    raise RuntimeError("PostgreSQL support not available. Install asyncpg for PostgreSQL support.")
                
                # Connect to default postgres database to create new database
                admin_url = settings.DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
                admin_engine = create_async_engine(admin_url)
                
                database_name = f"zphere_tenant_{organization_id}"
                
                # Use asyncpg directly for database creation (SQLAlchemy doesn't support this)
                # Derive admin connection params from DATABASE_URL first (override defaults)
                try:
                    from sqlalchemy.engine import make_url
                    url = make_url(settings.DATABASE_URL)
                    conn_params = {
                        'host': url.host or settings.DATABASE_HOST,
                        'port': url.port or settings.DATABASE_PORT,
                        'user': url.username or settings.DATABASE_USER,
                        'password': url.password or settings.DATABASE_PASSWORD,
                        'database': 'postgres',
                    }
                except Exception:
                    # Fallback to settings if parsing fails
                    conn_params = {
                        'host': settings.DATABASE_HOST,
                        'port': settings.DATABASE_PORT,
                        'user': settings.DATABASE_USER,
                        'password': settings.DATABASE_PASSWORD,
                        'database': 'postgres',
                    }
                
                # Remove empty values
                conn_params = {k: v for k, v in conn_params.items() if v is not None}
                
                conn = await asyncpg.connect(**conn_params)
                try:
                    # Check if database exists
                    result = await conn.fetchval(
                        "SELECT 1 FROM pg_database WHERE datname = $1", 
                        database_name
                    )
                    
                    if not result:
                        # Create database
                        await conn.execute(f'CREATE DATABASE "{database_name}"')
                    
                    # Ensure tables exist in the tenant database (idempotent)
                    engine = self._get_tenant_engine(organization_id)
                    async with engine.begin() as tenant_conn:
                        # Import all models to ensure they are registered with Base before create_all
                        from ..models import (
                            user, organization, project, task, customer, project_invoice,
                            project_comment, item, context_card, handoff_summary, decision_log,
                            knowledge_base, workspace, milestone, recurring_task, task_assignee, subscription, proposal, project_report_schedule
                        )
                        from ..models import focus
                        from ..models import goal
                        from ..models import ai
                        from ..models import chat
                        from ..models.tenant import todo
                        # Create all tables for tenant using the shared model metadata
                        await tenant_conn.run_sync(Base.metadata.create_all)
                    
                    return True
                finally:
                    await conn.close()
                    await admin_engine.dispose()
                    
        except Exception as e:
            print(f"Error creating tenant database for {organization_id}: {e}")
            return False
    
    def _get_tenant_engine(self, organization_id: str):
        """Get or create engine for a specific tenant"""
        if organization_id not in self._engines:
            tenant_url = self._get_tenant_database_url(organization_id)
            
            if settings.DATABASE_URL.startswith("sqlite"):
                engine = create_async_engine(tenant_url, echo=settings.DEBUG)
            else:
                engine = create_async_engine(
                    tenant_url,
                    echo=settings.DEBUG,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                )
            
            self._engines[organization_id] = engine
            self._session_makers[organization_id] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        
        return self._engines[organization_id]
    
    async def get_tenant_session(self, organization_id: str) -> AsyncSession:
        """Get database session for a specific tenant"""
        if organization_id not in self._session_makers:
            self._get_tenant_engine(organization_id)
        
        return self._session_makers[organization_id]()
    
    async def get_master_session(self) -> AsyncSession:
        """Get master database session"""
        return self.master_session_maker()
    
    async def delete_tenant_database(self, organization_id: str) -> bool:
        """Delete tenant database (use with caution!)"""
        try:
            # Close existing connections
            if organization_id in self._engines:
                await self._engines[organization_id].dispose()
                del self._engines[organization_id]
                del self._session_makers[organization_id]
            
            if settings.DATABASE_URL.startswith("sqlite"):
                import os
                db_path = f"./tenant_{organization_id}.db"
                if os.path.exists(db_path):
                    os.remove(db_path)
                return True
            else:
                # PostgreSQL: Drop database
                admin_url = settings.DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
                admin_engine = create_async_engine(admin_url)
                
                database_name = f"zphere_tenant_{organization_id}"
                
                # Derive admin connection params from settings or DATABASE_URL
                conn_params = {
                    'host': settings.DATABASE_HOST,
                    'port': settings.DATABASE_PORT,
                    'user': settings.DATABASE_USER,
                    'password': settings.DATABASE_PASSWORD,
                    'database': 'postgres'
                }
                
                try:
                    from sqlalchemy.engine import make_url
                    url = make_url(settings.DATABASE_URL)
                    conn_params.setdefault('host', url.host)
                    conn_params.setdefault('port', url.port)
                    conn_params.setdefault('user', url.username)
                    conn_params.setdefault('password', url.password)
                except Exception:
                    pass
                
                conn_params = {k: v for k, v in conn_params.items() if v}
                
                conn = await asyncpg.connect(**conn_params)
                try:
                    # Terminate connections to the database
                    await conn.execute(f"""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = '{database_name}' AND pid <> pg_backend_pid()
                    """)
                    
                    # Drop database
                    await conn.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
                    return True
                finally:
                    await conn.close()
                    await admin_engine.dispose()
                    
        except Exception as e:
            print(f"Error deleting tenant database for {organization_id}: {e}")
            return False
    
    async def close_all_connections(self):
        """Close all database connections"""
        # Close tenant engines
        for engine in self._engines.values():
            await engine.dispose()
        
        # Close master engine
        await self.master_engine.dispose()
        
        self._engines.clear()
        self._session_makers.clear()

# Global tenant manager instance
tenant_manager = TenantDatabaseManager()
# reload

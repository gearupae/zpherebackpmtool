from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from ..core.config import settings

# Base for all models
Base = declarative_base()

# Async engine for database operations
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

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base
        from ..models import (
            user, organization, project, task, customer, project_invoice, 
            project_comment, item, context_card, handoff_summary, decision_log, 
            knowledge_base, workspace, milestone, recurring_task, task_assignee, subscription, proposal, project_report_schedule
        )
        # Ensure newly added models are imported
        from ..models import focus  # imports FocusBlock
        from ..models import goal   # imports Goal, GoalChecklist, GoalProgress, GoalReminder
        from ..models import ai     # imports AI models
        from ..models import chat   # imports ChatRoom, ChatMessage
        from ..models.tenant import todo  # imports NoteSection, NoteTodo
        from ..models import task_document  # imports TaskDocument
        await conn.run_sync(Base.metadata.create_all)

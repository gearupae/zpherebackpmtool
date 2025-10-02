import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.database import Base
from app.models.chat import ChatRoom, ChatMessage


@pytest.mark.asyncio
async def test_chat_models_persist():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        # Create a room
        room = ChatRoom(organization_id="org1", name="General", slug="general")
        session.add(room)
        await session.commit()
        await session.refresh(room)

        # Post a message
        msg = ChatMessage(organization_id="org1", room_id=room.id, user_id="user1", content="Hello")
        session.add(msg)
        await session.commit()

        # Verify
        result = await session.execute(
            ChatMessage.__table__.select().where(ChatMessage.room_id == room.id)
        )
        rows = result.fetchall()
        assert len(rows) == 1

    await engine.dispose()

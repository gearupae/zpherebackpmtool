from __future__ import annotations
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, exists

from ....api.deps_tenant import get_tenant_db, get_current_active_user_master
from ....models.user import User
from ....models.chat import ChatRoom, ChatMessage, ChatRoomMember, ChatRoomType
from ....schemas.chat import ChatRoom as ChatRoomSchema, ChatRoomCreate, ChatMessage as ChatMessageSchema, ChatMessageCreate

router = APIRouter()


@router.get("/chat/users")
async def list_org_users(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    res = await db.execute(select(User).where(User.organization_id == current_user.organization_id, User.is_active == True).order_by(User.first_name.asc()))
    users = res.scalars().all()
    return [
        {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
        }
        for u in users
    ]


async def _get_or_create_default_room(db: AsyncSession, org_id: str) -> ChatRoom:
    stmt = select(ChatRoom).where(ChatRoom.organization_id == org_id, ChatRoom.slug == "general")
    res = await db.execute(stmt)
    room = res.scalar_one_or_none()
    if room:
        return room
    room = ChatRoom(organization_id=org_id, name="General", slug="general", description="Organization-wide chat")
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/chat/rooms", response_model=List[ChatRoomSchema])
async def list_rooms(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    # Ensure default room exists
    await _get_or_create_default_room(db, current_user.organization_id)

    # Return public rooms + rooms (dm/private) where current user is a member
    membership_exists = exists().where(
        and_(ChatRoomMember.room_id == ChatRoom.id, ChatRoomMember.user_id == current_user.id)
    )
    stmt = select(ChatRoom).where(
        ChatRoom.organization_id == current_user.organization_id,
        or_(ChatRoom.room_type == ChatRoomType.PUBLIC, membership_exists)
    ).order_by(ChatRoom.created_at.asc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/chat/rooms", response_model=ChatRoomSchema)
async def create_room(
    payload: ChatRoomCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    # Ensure unique slug per organization
    stmt = select(ChatRoom).where(ChatRoom.organization_id == current_user.organization_id, ChatRoom.slug == payload.slug)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Room slug already exists")

    room = ChatRoom(
        organization_id=current_user.organization_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        is_private=payload.is_private or False,
        room_type=ChatRoomType.PRIVATE if payload.is_private else ChatRoomType.PUBLIC,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/chat/rooms/{room_id}/messages", response_model=List[ChatMessageSchema])
async def list_messages(
    room_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(None, description="ISO timestamp; return messages sent before this time"),
) -> Any:
    # Verify room belongs to org
    room_res = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.organization_id == current_user.organization_id))
    room = room_res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    stmt = select(ChatMessage).where(
        ChatMessage.room_id == room_id,
        ChatMessage.organization_id == current_user.organization_id,
        ChatMessage.deleted == False,
    )
    if before:
        from datetime import datetime
        try:
            before_dt = datetime.fromisoformat(before)
            stmt = stmt.where(ChatMessage.sent_at < before_dt)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid 'before' timestamp")

    stmt = stmt.order_by(ChatMessage.sent_at.desc()).limit(limit)
    res = await db.execute(stmt)
    messages = list(reversed(res.scalars().all()))  # return ascending by time
    return messages


@router.post("/chat/rooms/{room_id}/messages", response_model=ChatMessageSchema)
async def post_message(
    room_id: str,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    # Verify room belongs to org
    room_res = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.organization_id == current_user.organization_id))
    room = room_res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    msg = ChatMessage(
        organization_id=current_user.organization_id,
        room_id=room_id,
        user_id=current_user.id,
        content=payload.content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Best-effort real-time broadcast via websocket manager
    try:
        from .websockets import send_chat_message
        await send_chat_message(room_id=room_id, message={
            "type": "chat_message",
            "room_id": room_id,
            "message_id": msg.id,
            "author_id": current_user.id,
            "author_name": f"{current_user.first_name} {current_user.last_name}",
            "content": msg.content,
            "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        })
    except Exception:
        pass

    return msg


@router.post("/chat/dm/{other_user_id}", response_model=ChatRoomSchema)
async def start_dm(
    other_user_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    if other_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot start a DM with yourself")

    # Validate other user in same organization
    ures = await db.execute(select(User).where(User.id == other_user_id, User.organization_id == current_user.organization_id))
    other_user = ures.scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found in your organization")

    # Deterministic slug for DM
    a, b = sorted([current_user.id, other_user_id])
    slug = f"dm-{a}-{b}"

    # Find or create the DM room
    rres = await db.execute(select(ChatRoom).where(ChatRoom.organization_id == current_user.organization_id, ChatRoom.slug == slug))
    room = rres.scalar_one_or_none()
    if not room:
        room = ChatRoom(
            organization_id=current_user.organization_id,
            name=f"DM: {current_user.first_name} & {other_user.first_name}",
            slug=slug,
            is_private=True,
            room_type=ChatRoomType.DM,
        )
        db.add(room)
        await db.flush()
        # Add members
        db.add_all([
            ChatRoomMember(organization_id=current_user.organization_id, room_id=room.id, user_id=current_user.id),
            ChatRoomMember(organization_id=current_user.organization_id, room_id=room.id, user_id=other_user_id),
        ])
        await db.commit()
        await db.refresh(room)

    else:
        # Ensure membership present
        mres = await db.execute(select(ChatRoomMember).where(ChatRoomMember.room_id == room.id, ChatRoomMember.user_id == current_user.id))
        if not mres.scalar_one_or_none():
            db.add(ChatRoomMember(organization_id=current_user.organization_id, room_id=room.id, user_id=current_user.id))
            await db.commit()
            await db.refresh(room)

    return room

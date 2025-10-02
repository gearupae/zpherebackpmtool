#!/usr/bin/env python3
"""
Seed a demo chat room and messages for the first active organization.

- Picks the first active organization from the master DB (or use ORG_ID env var)
- Ensures the tenant DB exists and has the Organization and a User cloned in
- Creates a 'general' chat room if missing and inserts a few messages

Usage:
  PYTHONPATH=backend backend/venv/bin/python backend/scripts/seed_chat_demo.py

You can override organization by setting ORG_ID=<uuid> in env.
"""
import os
import asyncio
from typing import Optional

from sqlalchemy import select

from app.db.tenant_manager import tenant_manager
from app.models.organization import Organization
from app.models.user import User
from app.models.chat import ChatRoom, ChatMessage


async def ensure_org_in_tenant(tenant_session, org: Organization):
    res = await tenant_session.execute(select(Organization).where(Organization.id == org.id))
    if not res.scalar_one_or_none():
        clone = Organization(
            id=org.id,
            name=org.name,
            slug=org.slug,
            description=org.description,
            domain=org.domain,
            is_active=org.is_active,
            subscription_tier=org.subscription_tier,
            max_users=org.max_users,
            max_projects=org.max_projects,
            settings=org.settings,
            branding=org.branding,
        )
        tenant_session.add(clone)
        await tenant_session.flush()


async def ensure_user_in_tenant(tenant_session, master_user: User):
    res = await tenant_session.execute(select(User).where(User.id == master_user.id))
    if not res.scalar_one_or_none():
        clone_user = User(
            id=master_user.id,
            email=master_user.email,
            username=master_user.username,
            first_name=master_user.first_name,
            last_name=master_user.last_name,
            hashed_password=master_user.hashed_password,
            organization_id=master_user.organization_id,
            role=master_user.role,
            status=master_user.status,
            is_active=master_user.is_active,
            is_verified=master_user.is_verified,
            timezone=master_user.timezone,
            phone=master_user.phone,
            bio=master_user.bio,
            address=getattr(master_user, "address", None),
            preferences=master_user.preferences,
            notification_settings=master_user.notification_settings,
            last_login=master_user.last_login,
            password_changed_at=master_user.password_changed_at,
            avatar_url=getattr(master_user, "avatar_url", None),
        )
        tenant_session.add(clone_user)
        await tenant_session.flush()


async def main():
    master_session = await tenant_manager.get_master_session()
    try:
        org_id = os.getenv("ORG_ID")
        org: Optional[Organization] = None
        if org_id:
            res = await master_session.execute(select(Organization).where(Organization.id == org_id))
            org = res.scalar_one_or_none()
        else:
            res = await master_session.execute(select(Organization).where(Organization.is_active == True))
            org = res.scalars().first()
        if not org:
            print("No active organization found in master DB. Create an org first.")
            return

        # Pick a user in this org
        user_res = await master_session.execute(select(User).where(User.organization_id == org.id, User.is_active == True))
        user = user_res.scalars().first()
        if not user:
            print(f"No active users found for org {org.id}. Create a user first.")
            return

        # Ensure tenant DB and connect
        await tenant_manager.create_tenant_database(org.id)
        tenant_session = await tenant_manager.get_tenant_session(org.id)
        try:
            await ensure_org_in_tenant(tenant_session, org)
            await ensure_user_in_tenant(tenant_session, user)
            await tenant_session.commit()

            # Ensure 'general' room
            room_res = await tenant_session.execute(
                select(ChatRoom).where(ChatRoom.organization_id == org.id, ChatRoom.slug == "general")
            )
            room = room_res.scalar_one_or_none()
            if not room:
                room = ChatRoom(organization_id=org.id, name="General", slug="general", description="Org-wide chat")
                tenant_session.add(room)
                await tenant_session.commit()
                await tenant_session.refresh(room)

            # Insert a few demo messages
            demo_messages = [
                "Welcome to the General room!",
                "This is a demo message to showcase real-time chat.",
                "Feel free to add your own messages.",
            ]
            for content in demo_messages:
                msg = ChatMessage(
                    organization_id=org.id,
                    room_id=room.id,
                    user_id=user.id,
                    content=content,
                )
                tenant_session.add(msg)
            await tenant_session.commit()

            print(f"Seeded chat demo in tenant DB for org {org.slug} ({org.id}). Room id: {room.id}")
        finally:
            await tenant_session.close()
    finally:
        await master_session.close()


if __name__ == "__main__":
    asyncio.run(main())

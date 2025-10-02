from __future__ import annotations
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....api.deps_tenant import get_tenant_db, get_current_active_user_master
from ....models.integration_hub import Integration, IntegrationType
from ....models.user import User
from ....schemas.email import EmailConfig, EmailConfigUpdate
from ....core.crypto import encrypt_json
from ....services.email_service import send_email_for_org

router = APIRouter()


async def _get_email_integration(db: AsyncSession, org_id: str) -> Optional[Integration]:
    stmt = select(Integration).where(
        Integration.organization_id == org_id,
        Integration.integration_type == IntegrationType.EMAIL
    )
    res = await db.execute(stmt)
    return res.scalars().first()


@router.get("/email/config", response_model=EmailConfig)
async def get_email_config(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    integ = await _get_email_integration(db, current_user.organization_id)
    if not integ:
        return EmailConfig(is_active=True, is_configured=False)

    cfg = integ.config or {}
    # Do not return sensitive credentials
    return EmailConfig(
        provider=cfg.get("provider"),
        host=cfg.get("host"),
        port=cfg.get("port", 587),
        security=cfg.get("security", "starttls"),
        username=cfg.get("username"),
        from_email=cfg.get("from_email"),
        from_name=cfg.get("from_name"),
        is_active=integ.is_active,
        is_configured=True,
    )


@router.post("/email/config", response_model=EmailConfig)
async def update_email_config(
    data: EmailConfigUpdate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    if data.security not in (None, "starttls", "ssl", "none"):
        raise HTTPException(status_code=400, detail="Invalid security value")

    integ = await _get_email_integration(db, current_user.organization_id)
    if not integ:
        integ = Integration(
            organization_id=current_user.organization_id,
            created_by_id=current_user.id,
            integration_type=IntegrationType.EMAIL,
            name="Email (SMTP)",
            description="Organization SMTP configuration",
            is_active=True,
            config={},
        )
        db.add(integ)

    cfg = integ.config or {}

    # Update config map
    if data.provider is not None:
        cfg["provider"] = data.provider
    if data.host is not None:
        cfg["host"] = data.host
    if data.port is not None:
        cfg["port"] = data.port
    if data.security is not None:
        cfg["security"] = data.security
    if data.username is not None:
        cfg["username"] = data.username
    if data.from_email is not None:
        cfg["from_email"] = data.from_email
    if data.from_name is not None:
        cfg["from_name"] = data.from_name

    # Update encrypted credentials if username/password provided
    if data.password is not None or data.username is not None:
        username = data.username if data.username is not None else cfg.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="Username is required when setting password")
        creds = {"username": username}
        if data.password is not None:
            creds["password"] = data.password
        integ.encrypted_credentials = encrypt_json(creds)

    integ.config = cfg
    if data.is_active is not None:
        integ.is_active = data.is_active

    await db.commit()
    await db.refresh(integ)

    return await get_email_config(current_user=current_user, db=db)


@router.post("/email/test")
async def send_test_email(
    payload: dict,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    to_email = payload.get("to")
    if not to_email:
        raise HTTPException(status_code=400, detail="Missing 'to' field")

    ok = await send_email_for_org(
        db,
        organization_id=current_user.organization_id,
        to_email=to_email,
        subject=payload.get("subject", "Test Email from Zphere"),
        body=payload.get("body", "Hello! This is a test email."),
        html=bool(payload.get("html", False)),
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Email send failed")
    return {"message": "Test email sent"}

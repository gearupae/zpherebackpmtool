import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.integration_hub import Integration, IntegrationType
from ..core.crypto import decrypt_json

SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USERNAME or 'no-reply@example.com')
SMTP_SECURITY = os.getenv('SMTP_SECURITY', 'starttls')  # starttls|ssl|none


DEFAULT_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'Zphere')


def _resolve_provider_defaults(provider: Optional[str]) -> Dict[str, Any]:
    provider = (provider or '').lower()
    if provider in ('gmail', 'gsuite', 'google', 'g-suite'):
        return {"host": "smtp.gmail.com", "port": 587, "security": "starttls"}
    if provider in ('outlook', 'office365', 'o365', 'microsoft'):
        return {"host": "smtp.office365.com", "port": 587, "security": "starttls"}
    return {}


def _send_smtp(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    from_email: str,
    from_name: Optional[str] = None,
    to_email: str,
    subject: str,
    body: str,
    html: bool = False,
    security: str = 'starttls',
) -> bool:
    try:
        if html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>" if from_name else from_email
        msg['To'] = to_email

        if security == 'ssl':
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                if security == 'starttls':
                    server.starttls()
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception:
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email using global SMTP env config if configured. Returns True on success or if SMTP not configured (no-op)."""
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        # No SMTP configured; treat as no-op success in dev
        return True
    return _send_smtp(
        host=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USERNAME,
        password=SMTP_PASSWORD,
        from_email=SMTP_FROM,
        from_name=DEFAULT_FROM_NAME,
        to_email=to_email,
        subject=subject,
        body=body,
        html=False,
        security=SMTP_SECURITY,
    )


async def _get_org_email_integration(db: AsyncSession, organization_id: str) -> Optional[Integration]:
    stmt = select(Integration).where(
        Integration.organization_id == organization_id,
        Integration.integration_type == IntegrationType.EMAIL
    )
    res = await db.execute(stmt)
    return res.scalars().first()


async def send_email_for_org(
    db: AsyncSession,
    *,
    organization_id: str,
    to_email: str,
    subject: str,
    body: str,
    html: bool = False,
) -> bool:
    """Send email using organization's configured SMTP (EMAIL integration). Falls back to env SMTP if not configured."""
    integ = await _get_org_email_integration(db, organization_id)
    if not integ or not integ.is_active:
        # Fallback to env-based send
        return send_email(to_email, subject, body)

    config = integ.config or {}
    creds = decrypt_json(integ.encrypted_credentials or '') if integ.encrypted_credentials else {}

    provider = (config.get('provider') or '').lower()
    defaults = _resolve_provider_defaults(provider)

    host = config.get('host') or defaults.get('host')
    port = int(config.get('port') or defaults.get('port') or 587)
    security = (config.get('security') or defaults.get('security') or 'starttls').lower()

    username = creds.get('username') or config.get('username')
    password = creds.get('password') or config.get('password')
    from_email = config.get('from_email') or username or SMTP_FROM
    from_name = config.get('from_name') or DEFAULT_FROM_NAME

    if not host or not username or not password:
        # Missing required settings; treat as success to avoid hard failure in dev
        return True

    return _send_smtp(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        from_name=from_name,
        to_email=to_email,
        subject=subject,
        body=body,
        html=html,
        security=security,
    )


def send_welcome_email(to_email: str, org_name: str) -> None:
    subject = f"Welcome to Zphere — {org_name} is ready"
    body = (
        f"Hi,\n\n"
        f"Your organization '{org_name}' has been created successfully. "
        f"You can log in and start using your workspace.\n\n"
        f"Best,\nZphere Team\n"
    )
    send_email(to_email, subject, body)

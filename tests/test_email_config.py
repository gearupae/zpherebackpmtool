import os
import asyncio
import pytest

from app.core.crypto import encrypt_str, decrypt_str, encrypt_json, decrypt_json
from app.services import email_service


class DummySMTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = False
        self.sent = []
    def starttls(self):
        self.started_tls = True
    def login(self, username, password):
        self.logged_in = (username, password)
    def sendmail(self, from_addr, to_addrs, msg):
        self.sent.append((from_addr, tuple(to_addrs), msg))
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class DummySMTP_SSL(DummySMTP):
    pass


@pytest.mark.asyncio
async def test_crypto_roundtrip():
    token = encrypt_str("hello")
    assert decrypt_str(token) == "hello"
    enc = encrypt_json({"a": 1})
    assert decrypt_json(enc) == {"a": 1}


def test_send_smtp_starttls(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP", DummySMTP)
    ok = email_service._send_smtp(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        from_email="from@example.com",
        from_name="From Name",
        to_email="to@example.com",
        subject="Subj",
        body="Body",
        html=False,
        security="starttls",
    )
    assert ok is True


def test_send_smtp_ssl(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", DummySMTP_SSL)
    ok = email_service._send_smtp(
        host="smtp.example.com",
        port=465,
        username="user",
        password="pass",
        from_email="from@example.com",
        from_name="From Name",
        to_email="to@example.com",
        subject="Subj",
        body="<b>Body</b>",
        html=True,
        security="ssl",
    )
    assert ok is True

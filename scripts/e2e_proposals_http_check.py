#!/usr/bin/env python3
import json
import sys
import time
import uuid
import urllib.request
import urllib.error
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:8000"


def http_request(method, path, data=None, headers=None):
    url = urljoin(BASE_URL, path)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in content_type:
                return resp.status, json.loads(raw.decode("utf-8")), resp.headers
            return resp.status, raw, resp.headers
    except urllib.error.HTTPError as e:
        try:
            payload = e.read().decode("utf-8")
            parsed = json.loads(payload)
        except Exception:
            parsed = {"error": payload}
        return e.code, parsed, getattr(e, 'headers', {})
    except Exception as e:
        return 0, {"error": str(e)}, {}


def login(email, password):
    code, data, _ = http_request(
        "POST", "/api/v1/auth/login", {"email": email, "password": password}
    )
    if code != 200:
        raise RuntimeError(f"Login failed for {email}: {code} {data}")
    return data["access_token"]


def register_user(email, password, first, last, org_name):
    code, data, _ = http_request(
        "POST",
        "/api/v1/auth/register",
        {
            "first_name": first,
            "last_name": last,
            "email": email,
            "password": password,
            "organization_name": org_name,
        },
    )
    if code != 200:
        raise RuntimeError(f"Register failed for {email}: {code} {data}")
    return data


def me(token):
    code, data, _ = http_request(
        "GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"/me failed: {code} {data}")
    return data


def create_customer(token, first, last, email):
    payload = {
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": None,
        "company_name": "Test Co",
        "customer_type": "client",
        "tags": ["e2e"],
    }
    code, data, _ = http_request(
        "POST", "/api/v1/customers/", payload, headers={"Authorization": f"Bearer {token}"}
    )
    if code != 201:
        raise RuntimeError(f"create_customer failed: {code} {data}")
    return data


def create_proposal(token, customer_id, title):
    payload = {
        "title": title,
        "description": "E2E Proposal",
        "proposal_type": "project",
        "content": {"items": []},
        "total_amount": 12345,
        "currency": "usd",
        "tags": ["e2e"],
        "customer_id": customer_id,
    }
    code, data, _ = http_request(
        "POST", "/api/v1/proposals/", payload, headers={"Authorization": f"Bearer {token}"}
    )
    if code != 201:
        raise RuntimeError(f"create_proposal failed: {code} {data}")
    return data


def list_proposals(token):
    code, data, _ = http_request(
        "GET", "/api/v1/proposals/?page=1&size=50", headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"list_proposals failed: {code} {data}")
    return data


def send_proposal(token, proposal_id):
    code, data, _ = http_request(
        "POST", f"/api/v1/proposals/{proposal_id}/send", headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"send_proposal failed: {code} {data}")


def accept_proposal(token, proposal_id):
    code, data, _ = http_request(
        "POST", f"/api/v1/proposals/{proposal_id}/accept", headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"accept_proposal failed: {code} {data}")


def reject_proposal(token, proposal_id, reason="Not a fit"):
    payload = {"rejection_reason": reason}
    code, data, _ = http_request(
        "POST", f"/api/v1/proposals/{proposal_id}/reject", payload, headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"reject_proposal failed: {code} {data}")


def get_pdf(token, proposal_id):
    code, _, headers = http_request(
        "GET", f"/api/v1/proposals/{proposal_id}/pdf", headers={"Authorization": f"Bearer {token}"}
    )
    if code != 200:
        raise RuntimeError(f"pdf failed: {code}")
    if "application/pdf" not in headers.get("Content-Type", ""):
        raise RuntimeError("pdf content-type check failed")


def main():
    report = {"backend_e2e": {}, "multi_tenant": {}}

    # Admin login (platform admin seeded)
    admin_token = login("admin@zphere.com", "admin123")
    admin_me = me(admin_token)

    # Prepare data under admin org
    cust = create_customer(admin_token, "E2E", "Client", f"client+{uuid.uuid4().hex[:8]}@example.com")
    prop = create_proposal(admin_token, cust["id"], f"E2E Proposal {uuid.uuid4().hex[:6]}")

    # Send, accept, PDF
    send_proposal(admin_token, prop["id"])
    accept_proposal(admin_token, prop["id"])  # Accept flow
    get_pdf(admin_token, prop["id"])          # PDF generation

    # Also test reject on a new proposal
    cust2 = create_customer(admin_token, "E2E2", "Client2", f"client2+{uuid.uuid4().hex[:8]}@example.com")
    prop2 = create_proposal(admin_token, cust2["id"], f"E2E Proposal {uuid.uuid4().hex[:6]}")
    send_proposal(admin_token, prop2["id"])
    reject_proposal(admin_token, prop2["id"], reason="Budget constraints")

    report["backend_e2e"] = {
        "admin_org_id": admin_me.get("organization_id"),
        "created_proposals": [prop["id"], prop2["id"]],
        "status": "ok",
    }

    # Multi-tenant isolation: create two orgs via registration
    email_a = f"tenantA+{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"tenantB+{uuid.uuid4().hex[:6]}@example.com"
    password = "Passw0rd!"

    reg_a = register_user(email_a, password, "Alice", "Alpha", "Org Alpha")
    reg_b = register_user(email_b, password, "Bob", "Beta", "Org Beta")

    token_a = login(email_a, password)
    token_b = login(email_b, password)

    me_a = me(token_a)
    me_b = me(token_b)

    # Create proposals in each tenant
    ca = create_customer(token_a, "C1", "A", f"ca+{uuid.uuid4().hex[:6]}@example.com")
    pa = create_proposal(token_a, ca["id"], "Tenant A Proposal")

    cb = create_customer(token_b, "C1", "B", f"cb+{uuid.uuid4().hex[:6]}@example.com")
    pb = create_proposal(token_b, cb["id"], "Tenant B Proposal")

    la = list_proposals(token_a)
    lb = list_proposals(token_b)

    ids_a = {item["id"] for item in la.get("items", [])}
    ids_b = {item["id"] for item in lb.get("items", [])}

    isolated = (pa["id"] in ids_a) and (pb["id"] in ids_b) and (pa["id"] not in ids_b) and (pb["id"] not in ids_a)

    report["multi_tenant"] = {
        "org_a": me_a.get("organization", {}).get("id") or me_a.get("organization_id"),
        "org_b": me_b.get("organization", {}).get("id") or me_b.get("organization_id"),
        "proposal_a": pa["id"],
        "proposal_b": pb["id"],
        "isolation_ok": isolated,
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()


"""MCP tool handlers for Kora authorization engine.

Five tools: kora_check_budget, kora_spend, kora_recent_activity, kora_health, kora_audit.
All outputs are deterministic templates. Uses httpx for HTTP calls.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime

import httpx

from .crypto import canonicalize, parse_agent_key, sign_message
from .templates import (
    render_budget,
    render_budget_error,
    render_spend_approved,
    render_spend_denied,
    render_spend_unavailable,
    render_recent_activity,
    render_no_admin_key,
    render_health_ok,
    render_health_unavailable,
    render_audit,
    render_audit_no_admin_key,
)


def handle_check_budget(
    secret: str,
    mandate_id: str,
    base_url: str,
) -> str:
    """Handle kora_check_budget tool call."""
    agent_id, signing_key = parse_agent_key(secret)
    body = {"mandate_id": mandate_id}
    canonical = canonicalize(body)
    signature = sign_message(canonical, signing_key)

    try:
        resp = httpx.post(
            f"{base_url}/v1/mandates/{mandate_id}/budget",
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Id": agent_id,
                "X-Agent-Signature": signature,
            },
            timeout=30,
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return render_health_unavailable("connection error")

    if resp.status_code == 404:
        return render_budget_error()
    if resp.status_code >= 500:
        return render_health_unavailable(f"HTTP {resp.status_code}")
    if resp.status_code >= 400:
        return render_budget_error()

    return render_budget(resp.json())


def handle_spend(
    secret: str,
    mandate_id: str,
    base_url: str,
    vendor: str,
    amount_cents: int,
    currency: str,
    reason: str,
) -> str:
    """Handle kora_spend tool call."""
    agent_id, signing_key = parse_agent_key(secret)
    intent_id = str(uuid.uuid4())
    nonce = base64.b64encode(os.urandom(16)).decode("ascii")
    ttl_seconds = 300

    signed_fields = {
        "intent_id": intent_id,
        "agent_id": agent_id,
        "mandate_id": mandate_id,
        "amount_cents": amount_cents,
        "currency": currency,
        "vendor_id": vendor,
        "nonce": nonce,
        "ttl_seconds": ttl_seconds,
    }
    canonical = canonicalize(signed_fields)
    signature = sign_message(canonical, signing_key)

    body = {
        "intent_id": intent_id,
        "agent_id": agent_id,
        "mandate_id": mandate_id,
        "amount_cents": amount_cents,
        "currency": currency,
        "vendor_id": vendor,
        "nonce": nonce,
        "ttl_seconds": ttl_seconds,
        "purpose": reason,
    }

    try:
        resp = httpx.post(
            f"{base_url}/v1/authorize",
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Signature": signature,
                "X-Agent-Id": agent_id,
            },
            timeout=30,
        )
    except httpx.ConnectError:
        return render_spend_unavailable("connection error")
    except httpx.TimeoutException:
        return render_spend_unavailable("timeout")

    if resp.status_code >= 500:
        return render_spend_unavailable(str(resp.status_code))

    if resp.status_code >= 400:
        raw = resp.json()
        error_msg = raw.get("message", raw.get("error", f"HTTP {resp.status_code}"))
        return f"\u274c Error: {error_msg}"

    raw = resp.json()
    decision = raw.get("decision", "DENIED")

    if decision == "APPROVED":
        return render_spend_approved(raw, vendor, amount_cents, currency, reason)
    else:
        return render_spend_denied(raw, vendor, amount_cents, currency)


def handle_recent_activity(
    admin_key: str,
    agent_id: str,
    mandate_id: str,
    base_url: str,
    limit: int = 5,
) -> str:
    """Handle kora_recent_activity tool call."""
    if not admin_key:
        return render_no_admin_key()

    limit = max(1, min(limit, 20))

    try:
        resp = httpx.get(
            f"{base_url}/v1/authorizations",
            params={
                "agent_id": agent_id,
                "mandate_id": mandate_id,
                "limit": limit,
            },
            headers={"Authorization": f"Bearer {admin_key}"},
            timeout=30,
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return render_health_unavailable("connection error")

    if resp.status_code >= 400:
        return f"Error fetching recent activity: HTTP {resp.status_code}"

    data = resp.json().get("data", [])
    now = datetime.now().astimezone()
    return render_recent_activity(data, now)


def handle_health(base_url: str) -> str:
    """Handle kora_health tool call. No auth required."""
    try:
        resp = httpx.get(f"{base_url}/health", timeout=10)
    except httpx.ConnectError:
        return render_health_unavailable("ConnectionError")
    except httpx.TimeoutException:
        return render_health_unavailable("TimeoutException")

    if resp.status_code != 200:
        return render_health_unavailable(f"HTTP {resp.status_code}")

    data = resp.json()
    return render_health_ok(
        version=data.get("version", "unknown"),
        database=data.get("database", "unknown"),
        uptime_seconds=data.get("uptime_seconds", 0),
    )


def handle_audit(
    mandate_id: str,
    admin_key: str,
    base_url: str,
    limit: int = 10,
    action: str | None = None,
) -> str:
    """Handle kora_audit tool call. Requires admin key."""
    if not admin_key:
        return render_audit_no_admin_key()

    limit = max(1, min(limit, 50))
    params: dict = {"target_id": mandate_id, "limit": limit}
    if action:
        params["action"] = action

    try:
        resp = httpx.get(
            f"{base_url}/v1/admin/audit",
            params=params,
            headers={"Authorization": f"Bearer {admin_key}"},
            timeout=30,
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return render_health_unavailable("connection error")

    if resp.status_code >= 400:
        return f"Error fetching audit log: HTTP {resp.status_code}"

    entries = resp.json().get("data", [])
    now = datetime.now().astimezone()
    return render_audit(entries, now)

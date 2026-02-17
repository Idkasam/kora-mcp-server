"""Kora MCP Server — stdio transport.

Exposes five tools: kora_check_budget, kora_spend, kora_recent_activity, kora_health, kora_audit.
All outputs are deterministic templates.

Usage:
    KORA_AGENT_SECRET=kora_agent_sk_... KORA_MANDATE=mandate_abc kora-mcp

Or configure in Claude Desktop's claude_desktop_config.json.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import get_config
from .crypto import parse_agent_key
from .tools import (
    handle_check_budget,
    handle_spend,
    handle_recent_activity,
    handle_health,
    handle_audit,
)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp_server = FastMCP(
    "kora",
    instructions="Kora authorization engine — check budgets, authorize spending, view activity, check health, view audit log.",
)

# Lazy initialization: config is created on first tool call
_config: dict | None = None


def _get_config() -> dict:
    global _config
    if _config is None:
        _config = get_config()
    return _config


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@mcp_server.tool(
    name="kora_check_budget",
    description="Check how much money you are allowed to spend. Call this BEFORE attempting any purchase.",
)
def kora_check_budget() -> str:
    """Check current spending budget."""
    cfg = _get_config()
    return handle_check_budget(
        secret=cfg["secret"],
        mandate_id=cfg["mandate"],
        base_url=cfg["base_url"],
    )


@mcp_server.tool(
    name="kora_spend",
    description="Request authorization to spend money. You MUST call this before making any purchase.",
)
def kora_spend(
    vendor: str,
    amount_cents: int,
    currency: str,
    reason: str,
) -> str:
    """Request authorization to spend money."""
    cfg = _get_config()
    return handle_spend(
        secret=cfg["secret"],
        mandate_id=cfg["mandate"],
        base_url=cfg["base_url"],
        vendor=vendor,
        amount_cents=amount_cents,
        currency=currency,
        reason=reason,
    )


@mcp_server.tool(
    name="kora_recent_activity",
    description="View your recent spending activity.",
)
def kora_recent_activity(limit: int = 5) -> str:
    """View recent spending activity."""
    cfg = _get_config()
    agent_id, _ = parse_agent_key(cfg["secret"])
    return handle_recent_activity(
        admin_key=cfg["admin_key"],
        agent_id=agent_id,
        mandate_id=cfg["mandate"],
        base_url=cfg["base_url"],
        limit=limit,
    )


@mcp_server.tool(
    name="kora_health",
    description="Check if Kora authorization service is available. Call this if you get errors from other Kora tools.",
)
def kora_health() -> str:
    """Check Kora service health."""
    cfg = _get_config()
    return handle_health(base_url=cfg["base_url"])


@mcp_server.tool(
    name="kora_audit",
    description="View recent admin actions on this mandate. Requires admin key.",
)
def kora_audit(limit: int = 10, action: str | None = None) -> str:
    """View recent admin actions on the mandate."""
    cfg = _get_config()
    return handle_audit(
        mandate_id=cfg["mandate"],
        admin_key=cfg["admin_key"],
        base_url=cfg["base_url"],
        limit=limit,
        action=action,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the MCP server with stdio transport."""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()

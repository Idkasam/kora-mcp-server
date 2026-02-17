"""MCP server configuration from environment variables."""
from __future__ import annotations

import os


def get_config() -> dict:
    """Read MCP server configuration from environment variables."""
    secret = os.environ.get("KORA_AGENT_SECRET", "")
    mandate = os.environ.get("KORA_MANDATE", "")
    if not secret:
        raise RuntimeError("KORA_AGENT_SECRET environment variable is required")
    if not mandate:
        raise RuntimeError("KORA_MANDATE environment variable is required")

    return {
        "secret": secret,
        "mandate": mandate,
        "admin_key": os.environ.get("KORA_ADMIN_KEY", ""),
        "base_url": os.environ.get("KORA_API_URL", "https://api.koraprotocol.com"),
    }

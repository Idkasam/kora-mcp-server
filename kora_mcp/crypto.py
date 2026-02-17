"""Cryptographic utilities for Kora agent authentication.

Handles agent key parsing, canonical JSON, and Ed25519 signing.
Uses PyNaCl for Ed25519.
"""
from __future__ import annotations

import base64
import json
from typing import Any

from nacl.signing import SigningKey


AGENT_SK_PREFIX = "kora_agent_sk_"


def parse_agent_key(key_string: str) -> tuple[str, SigningKey]:
    """Parse a Kora agent secret key string.

    Format: kora_agent_sk_<base64(agent_id:private_key_hex)>

    Returns:
        (agent_id, signing_key)
    """
    if not key_string.startswith(AGENT_SK_PREFIX):
        raise ValueError(f"Agent key must start with '{AGENT_SK_PREFIX}'")

    encoded = key_string[len(AGENT_SK_PREFIX):]
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Invalid base64 in agent key: {exc}") from exc

    if ":" not in decoded:
        raise ValueError("Agent key payload missing ':' separator")

    agent_id, private_hex = decoded.split(":", 1)

    if not agent_id:
        raise ValueError("Agent key has empty agent_id")

    try:
        seed = bytes.fromhex(private_hex)
    except ValueError as exc:
        raise ValueError(f"Invalid hex in private key: {exc}") from exc

    if len(seed) != 32:
        raise ValueError(f"Private key must be 32 bytes, got {len(seed)}")

    return agent_id, SigningKey(seed)


def _sort_keys_deep(obj: Any) -> Any:
    """Recursively sort dictionary keys for deterministic serialization."""
    if isinstance(obj, dict):
        return {k: _sort_keys_deep(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_keys_deep(item) for item in obj]
    return obj


def canonicalize(obj: dict[str, Any]) -> bytes:
    """Produce canonical JSON bytes (sorted keys, compact separators)."""
    sorted_obj = _sort_keys_deep(obj)
    return json.dumps(sorted_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_message(message: bytes, signing_key: SigningKey) -> str:
    """Sign a message with Ed25519 and return base64 signature."""
    signed = signing_key.sign(message)
    return base64.b64encode(signed.signature).decode("ascii")

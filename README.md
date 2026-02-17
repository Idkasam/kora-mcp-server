# Kora MCP Server

MCP server for [Kora](https://github.com/Idkasam/Kora) — deterministic authorization for AI agent spending.

Gives AI agents (Claude, GPT, etc.) the ability to check budgets, request spending authorization, and verify service health — all with cryptographic Ed25519 proofs.

## Quick Start

### Install

```bash
pip install kora-mcp-server
```

### Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kora": {
      "command": "kora-mcp",
      "env": {
        "KORA_API_URL": "https://api.koraprotocol.com",
        "KORA_AGENT_SECRET": "kora_agent_sk_...",
        "KORA_MANDATE": "mandate_abc123def456",
        "KORA_ADMIN_KEY": "kora_admin_sk_..."
      }
    }
  }
}
```

### Or run directly

```bash
KORA_AGENT_SECRET=kora_agent_sk_... \
KORA_MANDATE=mandate_abc123 \
kora-mcp
```

## Tools

| Tool | Auth | Description |
|------|------|-------------|
| `kora_check_budget` | Agent | Check remaining daily/monthly budget |
| `kora_spend` | Agent | Authorize a spend — returns APPROVED or DENIED with seal |
| `kora_recent_activity` | Admin | View recent authorization history |
| `kora_health` | None | Check if Kora is reachable |
| `kora_audit` | Admin | View recent admin actions on the mandate |

## Configuration

| Env Variable | Required | Description |
|---|---|---|
| `KORA_AGENT_SECRET` | Yes | Agent secret key (`kora_agent_sk_...`) |
| `KORA_MANDATE` | Yes | Mandate ID governing spending limits |
| `KORA_API_URL` | No | API base URL (default: `https://api.koraprotocol.com`) |
| `KORA_ADMIN_KEY` | No | Admin key for audit + activity tools |

## How It Works

1. AI agent calls `kora_check_budget` → sees remaining limits
2. Agent calls `kora_spend` with amount, vendor, currency, reason
3. Kora returns **APPROVED** (with Ed25519 cryptographic seal) or **DENIED** (with reason + suggestion)
4. Agent proceeds only if approved — denials include actionable hints for self-correction

**Fail-closed:** If Kora is unreachable, the agent gets a clear "DO NOT PROCEED" message. No silent failures.

## What is Kora?

Kora is a deterministic authorization engine for autonomous AI agent spending. It's not a bank, not a wallet, not a payment processor. Agents ask Kora "can I spend this?" and get a cryptographically signed yes or no.

- [Kora Repository](https://github.com/Idkasam/Kora)
- [API Reference](https://github.com/Idkasam/Kora/blob/main/docs/API_REFERENCE.md)
- [Patent: PCT/EP2025/053553](https://github.com/Idkasam/Kora)

# Kora MCP Server

**The Deterministic Authorization Gate for AI Agents**

Kora provides a cryptographically secure Go/No-Go layer for autonomous software. This Model Context Protocol (MCP) server enables LLMs (Claude, GPT-4, Cursor) to request explicit permission before initiating financial actions.

# kora-mcp-server

**MCP server for Kora — give any MCP client governed spending in seconds.**

Zero code. Add Kora as an MCP server. Your AI agent gets budget-checked, Ed25519-signed spending with no SDK integration needed.

## Install

```bash
pip install kora-mcp-server
```

## Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kora": {
      "command": "kora-mcp",
      "env": {
        "KORA_AGENT_SECRET": "kora_agent_sk_...",
        "KORA_MANDATE_ID": "mandate_abc123",
        "KORA_BASE_URL": "https://your-kora-server.com"
      }
    }
  }
}
```

Restart Claude Desktop. Done.

## Available tools

| Tool | Description |
|---|---|
| `kora_spend` | Authorize a spend — returns APPROVED + seal or DENIED + hint |
| `kora_check_budget` | Check daily/monthly remaining, velocity, time windows |
| `kora_recent_activity` | List recent authorizations |
| `kora_health` | Server health and version |
| `kora_audit` | Full audit trail for a mandate |

## How it works

Claude says "I need to spend $50 on AWS" → MCP server signs the request with Ed25519 → sends to Kora → 14-step deterministic pipeline → APPROVED or DENIED with actionable hint.

Every decision is cryptographically sealed. No ML. No guessing.

## Also available as

| Package | Description |
|---|---|
| [kora-sdk](https://github.com/Idkasam/kora-sdk) | Python + TypeScript SDK — 5 lines to authorized spend |
| [n8n-nodes-kora](https://github.com/Idkasam/n8n-nodes-kora) | n8n community node — visual workflow with two-output branching |

## Links

- **Website:** [koraprotocol.com](https://koraprotocol.com)
- **PyPI:** [kora-mcp-server](https://pypi.org/project/kora-mcp-server/)
- **Patent:** PCT/EP2025/053553

## License

Apache 2.0

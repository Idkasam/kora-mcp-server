# Kora MCP Server

**The Deterministic Authorization Gate for AI Agents**

Kora provides a cryptographically secure Go/No-Go layer for autonomous software. This Model Context Protocol (MCP) server enables LLMs (Claude, GPT-4, Cursor) to request explicit permission before initiating financial actions.

**Kora is not a wallet. It is the authority that governs the wallet.**

## Core Principles

**Fail-Closed Architecture:** If Kora is unreachable or a mandate is exceeded, the result is a hard DENIED. There are no "silent approvals."

**Cryptographic Ed25519 Seals:** Every approval contains an immutable seal. Agents receive verifiable proof that a mandate authorized the action.

**Anti-Hallucination Governance:** Agents stop "guessing" budget availability. They receive deterministic data, removing prompt-based ambiguity.

## The Kora Pattern

Kora transforms risky agentic behavior into a governed, four-stage lifecycle:

1. **Contextualize:** Agent calls `kora_check_budget` to verify if the task is feasible.
2. **Request:** Agent calls `kora_spend` with a specific intent (e.g., "Provisioning AWS EC2").
3. **Authorize:** Kora returns a Verdict: **APPROVED** (with seal) or **DENIED** (with hint).
4. **Execute:** The agent proceeds to the payment step only if a valid seal is present.

## Installation & Config

```bash
pip install kora-mcp-server
```

**Claude Desktop Configuration:**

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kora": {
      "command": "kora-mcp",
      "env": {
        "KORA_AGENT_SECRET": "kora_agent_sk_...",
        "KORA_MANDATE": "mandate_abc123...",
        "KORA_API_URL": "https://api.koraprotocol.com"
      }
    }
  }
}
```

## Tool Reference

| Tool | Capability | Access |
|------|-----------|--------|
| `kora_spend` | Request authorization for a vendor/amount | Agent |
| `kora_check_budget` | Retrieve real-time mandate liquidity | Agent |
| `kora_recent_activity` | Audit historical authorization decisions | Admin |
| `kora_health` | Verify service connectivity | Public |

## Institutional Resources

- **Documentation:** [docs.koraprotocol.com](https://docs.koraprotocol.com)
- **Ecosystem:** [n8n Nodes](https://github.com/Idkasam/Kora) | [Python SDK](https://github.com/Idkasam/Kora)
- **IP:** Patent PCT/EP2025/053553

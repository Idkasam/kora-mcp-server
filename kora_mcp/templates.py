"""Deterministic template rendering for MCP tool outputs.

All output is string interpolation. No randomness. No LLM calls.
Pure function: same inputs -> same output.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .format import format_amount


# ---------------------------------------------------------------------------
# Relative time formatting
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def format_relative(iso_timestamp: str, now: datetime) -> str:
    """Format an ISO timestamp as a relative time string.

    Rules:
    1. If target is today -> "today at HH:MM"
    2. If target is tomorrow -> "tomorrow at HH:MM"
    3. If target is within 7 days -> "{weekday} at HH:MM"
    4. If target is further -> "on {YYYY-MM-DD} at HH:MM"
    """
    target = datetime.fromisoformat(iso_timestamp)
    target_date = target.date()
    now_date = now.date()
    time_str = target.strftime("%H:%M")

    delta_days = (target_date - now_date).days
    if delta_days == 0:
        return f"today at {time_str}"
    elif delta_days == 1:
        return f"tomorrow at {time_str}"
    elif 2 <= delta_days <= 6:
        weekday = _WEEKDAY_NAMES[target.weekday()]
        return f"{weekday} at {time_str}"
    else:
        return f"on {target_date.isoformat()} at {time_str}"


# ---------------------------------------------------------------------------
# Budget template (kora_check_budget)
# ---------------------------------------------------------------------------

def compute_daily_percent(spent_cents: int, limit_cents: int) -> int:
    """Compute daily usage as integer percentage."""
    if limit_cents <= 0:
        return 0
    return round((spent_cents / limit_cents) * 100)


def render_budget(budget: dict) -> str:
    """Render budget check result as deterministic text."""
    currency = budget["currency"]
    fmt = lambda cents: format_amount(cents, currency)

    status = budget.get("status", "active")
    daily = budget["daily"]
    monthly = budget["monthly"]

    if status == "suspended":
        lines = [
            "\u26a0\ufe0f This mandate is SUSPENDED. Spending is not currently allowed.",
            "",
            "Budget (if reactivated):",
            f"\u2022 Daily: {fmt(daily['remaining_cents'])} remaining of {fmt(daily['limit_cents'])}",
            f"\u2022 Monthly: {fmt(monthly['remaining_cents'])} remaining of {fmt(monthly['limit_cents'])}",
            "",
            "Contact your administrator to reactivate.",
        ]
        return "\n".join(lines)

    # Active mandate
    now = datetime.now().astimezone()
    lines = ["Your current spending budget:"]
    lines.append(
        f"\u2022 Daily: {fmt(daily['remaining_cents'])} remaining of "
        f"{fmt(daily['limit_cents'])} (resets {format_relative(daily['resets_at'], now)})"
    )
    daily_percent = compute_daily_percent(daily["spent_cents"], daily["limit_cents"])
    lines.append(
        f"\u2022 Daily usage: {daily_percent}% ({fmt(daily['spent_cents'])} of {fmt(daily['limit_cents'])})"
    )
    lines.append(
        f"\u2022 Monthly: {fmt(monthly['remaining_cents'])} remaining of "
        f"{fmt(monthly['limit_cents'])} (resets {format_relative(monthly['resets_at'], now)})"
    )

    per_tx = budget.get("per_transaction_max_cents")
    if per_tx is not None:
        lines.append(f"\u2022 Per transaction max: {fmt(per_tx)}")

    allowed_vendors = budget.get("allowed_vendors")
    if allowed_vendors is not None:
        lines.append(f"\u2022 Allowed vendors: {', '.join(allowed_vendors)}")
    else:
        lines.append("\u2022 Vendors: unrestricted")

    allowed_categories = budget.get("allowed_categories")
    if allowed_categories is not None:
        lines.append(f"\u2022 Allowed categories: {', '.join(allowed_categories)}")

    time_window = budget.get("time_window")
    if time_window is not None:
        if time_window["currently_open"]:
            end_time = time_window["allowed_hours_local"]
            end_str = end_time["end"] if isinstance(end_time, dict) else end_time
            lines.append(f"\u2022 Spending window: Open now. Closes at {end_str} today.")
        else:
            next_open = time_window.get("next_open_at")
            if next_open:
                lines.append(
                    f"\u2022 Spending window: CLOSED. Opens {format_relative(next_open, now)}."
                )
            else:
                lines.append("\u2022 Spending window: CLOSED.")

    return "\n".join(lines)


def render_budget_error() -> str:
    """Render budget 404 (revoked/not found)."""
    return "\u274c Budget information unavailable. This mandate may not exist or may have been revoked."


# ---------------------------------------------------------------------------
# Spend templates (kora_spend)
# ---------------------------------------------------------------------------

def render_spend_approved(
    raw: dict,
    vendor: str,
    amount_cents: int,
    currency: str,
    reason: str,
) -> str:
    """Render approved spend result."""
    fmt = format_amount(amount_cents, currency)
    lines = [
        f"\u2705 APPROVED \u2014 {fmt} to {vendor}",
        f"Reason: {reason}",
        f"Decision: {raw.get('decision_id', '')}",
    ]

    limits = raw.get("limits_after_approval")
    if limits is not None:
        daily_remaining = limits.get("daily_remaining_cents")
        if daily_remaining is not None:
            lines.append(f"Daily remaining: {format_amount(daily_remaining, currency)}")

    return "\n".join(lines)


def render_spend_denied(
    raw: dict,
    vendor: str,
    amount_cents: int,
    currency: str,
) -> str:
    """Render denied spend result."""
    fmt = format_amount(amount_cents, currency)

    denial = raw.get("denial", {}) or {}
    message = denial.get("message", raw.get("reason_code", "Denied"))
    hint = denial.get("hint")
    actionable = denial.get("actionable", {}) or {}
    available_cents = actionable.get("available_cents")

    lines = [
        f"\u274c DENIED \u2014 Cannot spend {fmt} on {vendor}",
        f"Reason: {message}",
    ]

    if hint:
        lines.append(f"Suggestion: {hint}")

    if available_cents is not None and available_cents > 0:
        retry_fmt = format_amount(available_cents, currency)
        lines.append(f"You could retry with {retry_fmt} or less.")

    return "\n".join(lines)


def render_spend_unavailable(status_or_error: str) -> str:
    """Render fail-closed message when Kora is unreachable or returns 5xx."""
    lines = [
        f"\u274c AUTHORIZATION UNAVAILABLE \u2014 Kora returned {status_or_error}",
        "\u26a0\ufe0f You MUST NOT proceed with this payment.",
        "No authorization = No payment. This is a safety requirement.",
        "Try again later or call kora_health to check service status.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Recent activity template (kora_recent_activity)
# ---------------------------------------------------------------------------

def render_recent_activity(items: list[dict], now: datetime) -> str:
    """Render recent authorization activity."""
    if not items:
        return "No recent spending activity found."

    n = len(items)
    lines = [f"Recent spending activity (last {n}):"]

    today_approved_cents = 0
    today_denied_count = 0
    today_date = now.date()

    for i, item in enumerate(items, 1):
        decision = item.get("decision", "")
        amount = item.get("amount_cents", 0)
        currency = item.get("currency", "EUR")
        vendor = item.get("vendor_id", "unknown")
        purpose = item.get("purpose", "")
        reason_code = item.get("reason_code", "")
        evaluated_at = item.get("evaluated_at", "")

        fmt_amount = format_amount(amount, currency)
        rel_time = format_relative(evaluated_at, now) if evaluated_at else ""

        if decision == "APPROVED":
            purpose_str = f"({purpose})" if purpose else ""
            lines.append(f"{i}. \u2705 {fmt_amount} \u2192 {vendor} {purpose_str} \u2014 {rel_time}")
        else:
            lines.append(
                f"{i}. \u274c {fmt_amount} \u2192 {vendor} (DENIED: {reason_code}) \u2014 {rel_time}"
            )

        if evaluated_at:
            try:
                item_date = datetime.fromisoformat(evaluated_at).date()
                if item_date == today_date:
                    if decision == "APPROVED":
                        today_approved_cents += amount
                    else:
                        today_denied_count += 1
            except (ValueError, TypeError):
                pass

    summary_currency = items[0].get("currency", "EUR") if items else "EUR"
    today_total = format_amount(today_approved_cents, summary_currency)
    lines.append("")
    lines.append(f"Today's total: {today_total} approved, {today_denied_count} denied")

    return "\n".join(lines)


def render_no_admin_key() -> str:
    """Render message when admin key is not configured."""
    return "Recent activity is not available. An admin key is required for this feature."


# ---------------------------------------------------------------------------
# Health template (kora_health)
# ---------------------------------------------------------------------------

def format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string.

    Rules:
    - < 60 seconds → "{n} seconds"
    - < 3600 seconds → "{n} minutes"
    - < 86400 seconds → "{n} hours"
    - else → "{n} days"
    """
    s = int(seconds)
    if s < 60:
        return f"{s} seconds"
    elif s < 3600:
        return f"{s // 60} minutes"
    elif s < 86400:
        return f"{s // 3600} hours"
    else:
        return f"{s // 86400} days"


def render_health_ok(version: str, database: str, uptime_seconds: float) -> str:
    """Render healthy Kora status."""
    lines = [
        "\u2705 Kora is operational",
        f"Version: {version}",
        f"Database: {database}",
        f"Uptime: {format_uptime(uptime_seconds)}",
    ]
    return "\n".join(lines)


def render_health_unavailable(status_or_error: str) -> str:
    """Render unhealthy/unreachable Kora status."""
    lines = [
        "\u274c Kora is unavailable",
        f"Status: {status_or_error}",
        "\u26a0\ufe0f All spending requests will fail. Do NOT attempt any payments until Kora is available.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Audit template (kora_audit)
# ---------------------------------------------------------------------------

def render_audit(entries: list[dict], now: datetime) -> str:
    """Render audit log entries."""
    if not entries:
        return render_audit_empty()

    count = len(entries)
    lines = [f"Recent admin actions ({count}):"]

    for i, entry in enumerate(entries, 1):
        action = entry.get("action", "unknown")
        target_type = entry.get("target_type", "unknown")
        target_id = entry.get("target_id", "unknown")
        performed_at = entry.get("performed_at", "")
        admin_key_hash = entry.get("admin_key_hash", "")
        details = entry.get("details", {}) or {}

        rel_time = format_relative(performed_at, now) if performed_at else ""
        last_8 = admin_key_hash[-8:] if admin_key_hash else "unknown"

        lines.append(f"{i}. {action} on {target_type}/{target_id} \u2014 {rel_time}")
        lines.append(f"   By: admin key ...{last_8}")

        changed_fields = details.get("changed_fields")
        if changed_fields:
            if isinstance(changed_fields, list):
                lines.append(f"   Changed: {', '.join(changed_fields)}")
            else:
                lines.append(f"   Changed: {changed_fields}")

        reason = details.get("reason")
        if reason:
            lines.append(f"   Reason: {reason}")

    return "\n".join(lines)


def render_audit_empty() -> str:
    """Render empty audit log."""
    return "No admin actions found for this mandate."


def render_audit_no_admin_key() -> str:
    """Render message when admin key is not configured for audit."""
    return (
        "Audit log is not available. An admin key is required for this feature.\n"
        "Configure KORA_ADMIN_KEY in MCP server settings."
    )

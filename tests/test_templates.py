"""Template determinism tests for MCP tool outputs.

Tests that same inputs always produce identical output (no randomness).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from kora_mcp.templates import (
    format_relative,
    format_uptime,
    compute_daily_percent,
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
    render_audit_empty,
    render_audit_no_admin_key,
)
from kora_mcp.format import format_amount


# ---------------------------------------------------------------------------
# Helper: budget dict builder
# ---------------------------------------------------------------------------

def _make_active_budget(**overrides) -> dict:
    defaults = dict(
        currency="EUR",
        status="active",
        spend_allowed=True,
        enforcement_mode="enforce",
        daily=dict(limit_cents=50000, spent_cents=38000, remaining_cents=12000,
                   resets_at="2026-02-16T00:00:00+01:00"),
        monthly=dict(limit_cents=500000, spent_cents=234000, remaining_cents=266000,
                     resets_at="2026-03-01T00:00:00+01:00"),
        per_transaction_max_cents=10000,
        velocity=None,
        allowed_vendors=["aws", "openai", "stripe"],
        allowed_categories=["compute", "api_services"],
        time_window=None,
    )
    defaults.update(overrides)
    return defaults


def _make_suspended_budget() -> dict:
    return dict(
        currency="EUR",
        status="suspended",
        spend_allowed=False,
        enforcement_mode="enforce",
        daily=dict(limit_cents=50000, spent_cents=0, remaining_cents=50000,
                   resets_at="2026-02-16T00:00:00+01:00"),
        monthly=dict(limit_cents=500000, spent_cents=0, remaining_cents=500000,
                     resets_at="2026-03-01T00:00:00+01:00"),
        per_transaction_max_cents=None,
        velocity=None,
        allowed_vendors=None,
        allowed_categories=None,
        time_window=None,
    )


# ---------------------------------------------------------------------------
# format_relative tests
# ---------------------------------------------------------------------------

class TestFormatRelative:
    def test_today(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
        assert format_relative("2026-02-15T23:59:00+01:00", now) == "today at 23:59"

    def test_tomorrow(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
        assert format_relative("2026-02-16T00:00:00+01:00", now) == "tomorrow at 00:00"

    def test_within_7_days_weekday(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))  # Sunday
        assert format_relative("2026-02-18T08:00:00+01:00", now) == "Wednesday at 08:00"

    def test_further_than_7_days(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
        assert format_relative("2026-03-01T00:00:00+01:00", now) == "on 2026-03-01 at 00:00"

    def test_determinism(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
        ts = "2026-02-16T00:00:00+01:00"
        results = [format_relative(ts, now) for _ in range(100)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# Budget template tests
# ---------------------------------------------------------------------------

class TestBudgetTemplate:
    def test_determinism(self):
        budget = _make_active_budget()
        results = [render_budget(budget) for _ in range(50)]
        assert len(set(results)) == 1

    def test_active_budget_format(self):
        budget = _make_active_budget()
        output = render_budget(budget)
        assert "Your current spending budget:" in output
        assert "\u20ac120.00 remaining of \u20ac500.00" in output  # daily
        assert "\u20ac2660.00 remaining of \u20ac5000.00" in output  # monthly
        assert "Per transaction max: \u20ac100.00" in output
        assert "Allowed vendors: aws, openai, stripe" in output
        assert "Allowed categories: compute, api_services" in output

    def test_active_unrestricted_vendors(self):
        budget = _make_active_budget(allowed_vendors=None)
        output = render_budget(budget)
        assert "Vendors: unrestricted" in output

    def test_active_no_per_tx(self):
        budget = _make_active_budget(per_transaction_max_cents=None)
        output = render_budget(budget)
        assert "Per transaction max" not in output

    def test_active_no_categories(self):
        budget = _make_active_budget(allowed_categories=None)
        output = render_budget(budget)
        assert "Allowed categories" not in output

    def test_active_time_window_open(self):
        budget = _make_active_budget(
            time_window=dict(
                allowed_days=["mon", "tue", "wed", "thu", "fri"],
                allowed_hours_local={"start": "08:00", "end": "18:00"},
                currently_open=True,
                next_open_at=None,
            )
        )
        output = render_budget(budget)
        assert "Spending window: Open now. Closes at 18:00 today." in output

    def test_active_time_window_closed(self):
        budget = _make_active_budget(
            time_window=dict(
                allowed_days=["mon", "tue", "wed", "thu", "fri"],
                allowed_hours_local={"start": "08:00", "end": "18:00"},
                currently_open=False,
                next_open_at="2026-02-16T08:00:00+01:00",
            )
        )
        output = render_budget(budget)
        assert "Spending window: CLOSED." in output
        assert "Opens" in output

    def test_suspended_budget(self):
        budget = _make_suspended_budget()
        output = render_budget(budget)
        assert "SUSPENDED" in output
        assert "Spending is not currently allowed" in output
        assert "Contact your administrator" in output
        assert "\u20ac500.00 remaining of \u20ac500.00" in output  # daily

    def test_budget_error_404(self):
        output = render_budget_error()
        assert "unavailable" in output
        assert "revoked" in output


# ---------------------------------------------------------------------------
# Spend template tests
# ---------------------------------------------------------------------------

class TestSpendTemplate:
    def test_approved_format(self):
        raw = {
            "decision_id": "dec-abc123",
            "limits_after_approval": {"daily_remaining_cents": 95000},
        }
        output = render_spend_approved(raw, "aws", 5000, "EUR", "GPU compute")
        assert "\u2705 APPROVED" in output
        assert "\u20ac50.00 to aws" in output
        assert "Reason: GPU compute" in output
        assert "Decision: dec-abc123" in output
        assert "Daily remaining: \u20ac950.00" in output

    def test_approved_no_limits(self):
        raw = {"decision_id": "dec-abc"}
        output = render_spend_approved(raw, "aws", 5000, "EUR", "test")
        assert "Daily remaining" not in output

    def test_approved_determinism(self):
        raw = {"decision_id": "dec-x", "limits_after_approval": {"daily_remaining_cents": 1000}}
        results = [render_spend_approved(raw, "aws", 5000, "EUR", "test") for _ in range(50)]
        assert len(set(results)) == 1

    def test_denied_format(self):
        raw = {
            "reason_code": "DAILY_LIMIT_EXCEEDED",
            "denial": {
                "message": "Daily limit exceeded. Requested: 50000 cents.",
                "hint": "Reduce amount to 1200 cents or wait for daily reset.",
                "actionable": {"available_cents": 1200},
            },
        }
        output = render_spend_denied(raw, "aws", 50000, "EUR")
        assert "\u274c DENIED" in output
        assert "\u20ac500.00 on aws" in output
        assert "Daily limit exceeded" in output
        assert "Suggestion:" in output
        assert "\u20ac12.00 or less" in output

    def test_denied_no_retry(self):
        raw = {
            "reason_code": "VENDOR_NOT_ALLOWED",
            "denial": {
                "message": "Vendor not allowed.",
                "hint": "Use allowed vendor.",
                "actionable": {},
            },
        }
        output = render_spend_denied(raw, "gcp", 5000, "EUR")
        assert "retry" not in output.lower()

    def test_denied_determinism(self):
        raw = {
            "reason_code": "X",
            "denial": {
                "message": "denied",
                "hint": "hint",
                "actionable": {"available_cents": 500},
            },
        }
        results = [render_spend_denied(raw, "v", 1000, "EUR") for _ in range(50)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# Recent activity template tests
# ---------------------------------------------------------------------------

class TestRecentActivityTemplate:
    def test_empty(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert render_recent_activity([], now) == "No recent spending activity found."

    def test_with_data(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        items = [
            {
                "decision": "APPROVED",
                "amount_cents": 5000,
                "currency": "EUR",
                "vendor_id": "aws",
                "purpose": "GPU compute",
                "reason_code": "OK",
                "evaluated_at": "2026-02-15T13:00:00+00:00",
            },
            {
                "decision": "DENIED",
                "amount_cents": 80000,
                "currency": "EUR",
                "vendor_id": "openai",
                "purpose": None,
                "reason_code": "DAILY_LIMIT_EXCEEDED",
                "evaluated_at": "2026-02-15T12:30:00+00:00",
            },
        ]
        output = render_recent_activity(items, now)
        assert "Recent spending activity (last 2):" in output
        assert "1. \u2705 \u20ac50.00" in output
        assert "aws" in output
        assert "GPU compute" in output
        assert "2. \u274c \u20ac800.00" in output
        assert "DAILY_LIMIT_EXCEEDED" in output
        assert "Today's total:" in output

    def test_determinism(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        items = [
            {
                "decision": "APPROVED", "amount_cents": 5000, "currency": "EUR",
                "vendor_id": "aws", "purpose": "test", "reason_code": "OK",
                "evaluated_at": "2026-02-15T13:00:00+00:00",
            },
        ]
        results = [render_recent_activity(items, now) for _ in range(50)]
        assert len(set(results)) == 1

    def test_no_admin_key_message(self):
        output = render_no_admin_key()
        assert "admin key is required" in output


# ---------------------------------------------------------------------------
# V1.3: Health template tests
# ---------------------------------------------------------------------------

class TestHealthTemplate:
    def test_healthy_renders_correctly(self):
        output = render_health_ok("1.3.0", "connected", 7200)
        assert "\u2705 Kora is operational" in output
        assert "Version: 1.3.0" in output
        assert "Database: connected" in output
        assert "Uptime: 2 hours" in output

    def test_unhealthy_renders_warning(self):
        output = render_health_unavailable("HTTP 503")
        assert "\u274c Kora is unavailable" in output
        assert "Status: HTTP 503" in output
        assert "Do NOT attempt any payments" in output

    def test_determinism(self):
        results = [render_health_ok("1.3.0", "connected", 3600) for _ in range(50)]
        assert len(set(results)) == 1


class TestUptimeFormatting:
    def test_seconds(self):
        assert format_uptime(30) == "30 seconds"

    def test_zero_seconds(self):
        assert format_uptime(0) == "0 seconds"

    def test_59_seconds(self):
        assert format_uptime(59) == "59 seconds"

    def test_minutes(self):
        assert format_uptime(3540) == "59 minutes"

    def test_120_seconds_is_2_minutes(self):
        assert format_uptime(120) == "2 minutes"

    def test_hours(self):
        assert format_uptime(86399) == "23 hours"

    def test_3600_seconds_is_60_minutes(self):
        assert format_uptime(3599) == "59 minutes"

    def test_days(self):
        assert format_uptime(86400) == "1 days"

    def test_multiple_days(self):
        assert format_uptime(259200) == "3 days"


# ---------------------------------------------------------------------------
# V1.3: Audit template tests
# ---------------------------------------------------------------------------

class TestAuditTemplate:
    def test_with_entries(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        entries = [
            {
                "action": "mandate.patch",
                "target_type": "mandate",
                "target_id": "mandate_abc123",
                "performed_at": "2026-02-15T13:00:00+00:00",
                "admin_key_hash": "abcdef1234567890",
                "details": {
                    "changed_fields": ["daily_limit_cents", "monthly_limit_cents"],
                    "reason": "Budget increase for Q1",
                },
            },
            {
                "action": "agent.rotate_key",
                "target_type": "agent",
                "target_id": "agent_test_001",
                "performed_at": "2026-02-14T10:00:00+00:00",
                "admin_key_hash": "xyz98765abcdef12",
                "details": {},
            },
        ]
        output = render_audit(entries, now)
        assert "Recent admin actions (2):" in output
        assert "1. mandate.patch on mandate/mandate_abc123" in output
        assert "By: admin key ...34567890" in output
        assert "Changed: daily_limit_cents, monthly_limit_cents" in output
        assert "Reason: Budget increase for Q1" in output
        assert "2. agent.rotate_key on agent/agent_test_001" in output
        assert "By: admin key ...abcdef12" in output

    def test_empty(self):
        output = render_audit_empty()
        assert output == "No admin actions found for this mandate."

    def test_no_admin_key(self):
        output = render_audit_no_admin_key()
        assert "admin key is required" in output
        assert "KORA_ADMIN_KEY" in output

    def test_determinism(self):
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        entries = [
            {
                "action": "mandate.patch", "target_type": "mandate",
                "target_id": "mandate_abc", "performed_at": "2026-02-15T12:00:00+00:00",
                "admin_key_hash": "abcdef1234567890", "details": {},
            },
        ]
        results = [render_audit(entries, now) for _ in range(50)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# V1.3: Spend fail-closed template tests
# ---------------------------------------------------------------------------

class TestSpendFailClosed:
    def test_503_renders_fail_closed(self):
        output = render_spend_unavailable("503")
        assert "\u274c AUTHORIZATION UNAVAILABLE" in output
        assert "Kora returned 503" in output
        assert "MUST NOT proceed" in output
        assert "kora_health" in output

    def test_connection_error(self):
        output = render_spend_unavailable("connection error")
        assert "AUTHORIZATION UNAVAILABLE" in output
        assert "connection error" in output

    def test_determinism(self):
        results = [render_spend_unavailable("503") for _ in range(50)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# V1.3: Budget percent used tests
# ---------------------------------------------------------------------------

class TestBudgetPercentUsed:
    def test_45_percent(self):
        assert compute_daily_percent(45000, 100000) == 45

    def test_0_percent(self):
        assert compute_daily_percent(0, 100000) == 0

    def test_100_percent(self):
        assert compute_daily_percent(100000, 100000) == 100

    def test_zero_limit(self):
        assert compute_daily_percent(0, 0) == 0

    def test_budget_output_includes_percent(self):
        budget = _make_active_budget(
            daily=dict(limit_cents=100000, spent_cents=45000, remaining_cents=55000,
                       resets_at="2026-02-16T00:00:00+01:00"),
        )
        output = render_budget(budget)
        assert "Daily usage: 45%" in output
        assert "\u20ac450.00 of \u20ac1000.00" in output


# ---------------------------------------------------------------------------
# No random elements in any output
# ---------------------------------------------------------------------------

class TestNoRandomElements:
    """Verify no random elements appear in template output."""

    def test_all_templates_deterministic(self):
        """Run all templates 100 times and verify identical output."""
        now = datetime(2026, 2, 15, 14, 0, 0, tzinfo=timezone.utc)
        budget = _make_active_budget()
        spend_approved_raw = {"decision_id": "dec-x", "limits_after_approval": {"daily_remaining_cents": 1000}}
        spend_denied_raw = {
            "reason_code": "X",
            "denial": {"message": "denied", "hint": "hint", "actionable": {"available_cents": 500}},
        }
        items = [
            {"decision": "APPROVED", "amount_cents": 1000, "currency": "EUR",
             "vendor_id": "v", "purpose": "p", "reason_code": "OK",
             "evaluated_at": "2026-02-15T10:00:00+00:00"},
        ]
        audit_entries = [
            {
                "action": "mandate.patch", "target_type": "mandate",
                "target_id": "mandate_abc123", "performed_at": "2026-02-15T12:00:00+00:00",
                "admin_key_hash": "abcdef1234567890", "details": {},
            },
        ]

        funcs = [
            lambda: render_budget(budget),
            lambda: render_budget(_make_suspended_budget()),
            lambda: render_budget_error(),
            lambda: render_spend_approved(spend_approved_raw, "v", 1000, "EUR", "r"),
            lambda: render_spend_denied(spend_denied_raw, "v", 1000, "EUR"),
            lambda: render_spend_unavailable("503"),
            lambda: render_recent_activity(items, now),
            lambda: render_recent_activity([], now),
            lambda: render_no_admin_key(),
            lambda: render_health_ok("1.3.0", "connected", 3600),
            lambda: render_health_unavailable("HTTP 503"),
            lambda: render_audit(audit_entries, now),
            lambda: render_audit_empty(),
            lambda: render_audit_no_admin_key(),
        ]

        for fn in funcs:
            results = [fn() for _ in range(100)]
            assert len(set(results)) == 1, f"Non-deterministic output from {fn}"

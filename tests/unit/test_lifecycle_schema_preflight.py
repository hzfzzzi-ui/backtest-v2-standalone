import json
from unittest.mock import MagicMock

import pytest

from backend.core.services import mobile_execution_service as execution
from backend.core.services import mobile_ops_service as mobile_ops
from backend.core.services import ops_domain_pg as pg
from backend.core.services import transaction_lifecycle_service as lifecycle


def _files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _seed(root, *, expires_at=None):
    ticket = {"ticket_id": "isolated-ticket", "suggestion_id": "isolated-suggestion", "status": "approved_pending", "expires_at": expires_at}
    path = root / "mobile_ops" / "approval_tickets" / "isolated-ticket.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ticket), encoding="utf-8")
    return ticket, path


@pytest.fixture
def missing_schema(monkeypatch):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"relation": None}
    monkeypatch.setattr(pg, "connect", lambda: conn)
    return conn, cursor


def test_missing_schema_rejects_ticket_create_before_any_file_write(tmp_path, missing_schema):
    before = _files(tmp_path)
    with pytest.raises(pg.OpsDomainSchemaMissing, match="schema must be provisioned separately"):
        mobile_ops.create_ticket_from_confirmed_action(
            tmp_path, card={"suggestion_id": "isolated-suggestion"}, decision="approve", operator="test",
            idempotency_key="isolated-key", confirm_payload={}, now_ts=1000000,
        )
    assert _files(tmp_path) == before


def test_missing_schema_rejects_revoke_before_any_file_write(tmp_path, missing_schema):
    _seed(tmp_path)
    before = _files(tmp_path)
    with pytest.raises(pg.OpsDomainSchemaMissing):
        mobile_ops.revoke_ticket(tmp_path, ticket_id="isolated-ticket", operator="test", reason="test", now_ts=1000000)
    assert _files(tmp_path) == before


def test_missing_schema_rejects_expiry_before_any_file_write(tmp_path, missing_schema):
    ticket, path = _seed(tmp_path, expires_at="1970-01-01T00:00:01+00:00")
    ticket["_path"] = str(path)
    before = _files(tmp_path)
    with pytest.raises(pg.OpsDomainSchemaMissing):
        mobile_ops._maybe_expire_ticket_locked(tmp_path, ticket, now_ts=1000000)
    assert _files(tmp_path) == before


def test_missing_schema_rejects_execution_event_before_any_file_write(tmp_path, missing_schema):
    ticket, _ = _seed(tmp_path)
    before = _files(tmp_path)
    with pytest.raises(pg.OpsDomainSchemaMissing):
        execution._apply_status_transition_locked(
            tmp_path, ticket, new_status="claimed", executor_id="test", now_ts=1000000
        )
    assert _files(tmp_path) == before


def test_preflight_keeps_existing_file_fallback_if_database_unavailable(monkeypatch):
    def unavailable():
        raise pg.OpsDomainDbUnavailable("offline")
    monkeypatch.setattr(pg, "connect", unavailable)
    lifecycle.preflight_transaction_schema()


def test_missing_schema_returns_explicit_http_error(test_client, monkeypatch):
    from backend.api.mobile import impl

    monkeypatch.setattr(impl, "require_mobile_session", lambda request: None)
    def unavailable(*args, **kwargs):
        raise pg.OpsDomainSchemaMissing("schema must be provisioned separately")
    monkeypatch.setattr(impl, "list_approval_tickets", unavailable)
    response = test_client.get("/api/mobile/approval-tickets", headers={"host": "192.168.1.8"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "transaction lifecycle storage is not initialized",
        "code": "transaction_lifecycle_schema_missing",
    }


def test_dashboard_degrades_without_fabricating_transaction_data(tmp_path, monkeypatch):
    from backend.core.services import mobile_dashboard_service as dashboard
    from tests.unit.test_mobile_dashboard_service import _build_results_root

    results_root, _ = _build_results_root(tmp_path)
    before = _files(results_root)
    def unavailable(*args, **kwargs):
        raise pg.OpsDomainSchemaMissing("schema must be provisioned separately")
    def must_not_run(*args, **kwargs):
        raise AssertionError("transaction-derived content must not be generated")
    monkeypatch.setattr(dashboard, "load_mobile_control_state", unavailable)
    monkeypatch.setattr(dashboard, "list_execution_tickets", must_not_run)
    monkeypatch.setattr(dashboard, "build_mobile_daily_briefing", must_not_run)
    monkeypatch.setattr(dashboard, "build_mobile_notification_feed", must_not_run)
    payload = dashboard.build_mobile_dashboard(results_root)
    assert payload["status"] == "degraded"
    assert payload["lifecycle_status"] == {"status": "unavailable", "reason": "transaction_lifecycle_schema_missing"}
    assert payload["experiment"] is not None
    assert payload["market"] is not None
    assert payload["guidance"]["pending_tickets"] is None
    assert payload["guidance"]["pending_count"] is None
    assert payload["guidance"]["execution_tickets"] is None
    assert payload["guidance"]["execution_count"] is None
    assert payload["risk_flags"]["risk_locked"] is None
    assert payload["risk_flags"]["executor_available"] is None
    assert payload["briefing"]["status"] == "unavailable"
    assert payload["notifications"]["items"] is None
    assert payload["notifications"]["count"] is None
    assert _files(results_root) == before


def test_dashboard_http_remains_readable_when_lifecycle_schema_missing(test_client, tmp_path, monkeypatch):
    from backend.api.mobile import impl
    from backend.core.services import mobile_dashboard_service as dashboard
    from tests.unit.test_mobile_dashboard_service import _build_results_root

    results_root, _ = _build_results_root(tmp_path)
    monkeypatch.setattr(impl, "require_mobile_session", lambda request: None)
    monkeypatch.setattr(impl, "_results_root", lambda: results_root)
    def unavailable(*args, **kwargs):
        raise pg.OpsDomainSchemaMissing("schema must be provisioned separately")
    monkeypatch.setattr(dashboard, "load_mobile_control_state", unavailable)
    response = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["guidance"]["pending_count"] is None
    assert response.json()["experiment"] is not None

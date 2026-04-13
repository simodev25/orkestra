# tests/test_lab/test_update_run.py
"""Tests unitaires pour la whitelist et la logique de update_run()."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.test_lab.execution_engine import (
    _ALLOWED_UPDATE_FIELDS,
    update_run,
)


class TestAllowedFieldsWhitelist:
    """Vérifie que la whitelist contient exactement les colonnes attendues."""

    def test_contains_status(self):
        assert "status" in _ALLOWED_UPDATE_FIELDS

    def test_contains_started_at(self):
        assert "started_at" in _ALLOWED_UPDATE_FIELDS

    def test_contains_ended_at(self):
        assert "ended_at" in _ALLOWED_UPDATE_FIELDS

    def test_contains_all_expected_fields(self):
        expected = {
            "status", "final_output", "score", "verdict", "summary",
            "error_message", "assertion_results", "diagnostic_results",
            "iteration_count", "duration_ms", "started_at", "ended_at",
        }
        assert expected == _ALLOWED_UPDATE_FIELDS

    def test_does_not_contain_arbitrary_column(self):
        assert "injected_col" not in _ALLOWED_UPDATE_FIELDS

    def test_does_not_contain_id(self):
        # On ne doit pas pouvoir écraser la PK via update_run
        assert "id" not in _ALLOWED_UPDATE_FIELDS


class TestUpdateRunValidation:
    """update_run() valide les champs AVANT toute requête SQL."""

    def test_raises_on_unknown_field(self):
        with pytest.raises(ValueError, match="disallowed fields"):
            update_run("run_123", unknown_col="value")

    def test_raises_on_multiple_unknown_fields(self):
        with pytest.raises(ValueError, match="disallowed fields"):
            update_run("run_123", status="running", injected="x", another="y")

    def test_raises_names_the_bad_fields(self):
        with pytest.raises(ValueError, match="bad_field"):
            update_run("run_123", bad_field="x")

    def test_no_error_on_empty_call(self):
        # Aucun champ → retour immédiat, pas de requête SQL
        update_run("run_123")  # ne doit pas lever

    def test_valid_fields_reach_sql(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch(
            "app.services.test_lab.execution_engine._get_sync_engine",
            return_value=mock_engine,
        ):
            update_run("run_abc", status="running")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        sql_text = str(call_args[0][0])
        assert "status" in sql_text
        assert "run_abc" in str(call_args[0][1])

    def test_started_at_reaches_sql(self):
        """Régression : started_at était rejeté avant le fix du 2026-04-13."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch(
            "app.services.test_lab.execution_engine._get_sync_engine",
            return_value=mock_engine,
        ):
            # Ne doit pas lever ValueError
            update_run("run_xyz", status="running", started_at=now)

        mock_conn.execute.assert_called_once()

    def test_ended_at_reaches_sql(self):
        """Régression : ended_at était rejeté avant le fix du 2026-04-13."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch(
            "app.services.test_lab.execution_engine._get_sync_engine",
            return_value=mock_engine,
        ):
            update_run("run_xyz", status="failed", ended_at=now, error_message="err")

        mock_conn.execute.assert_called_once()

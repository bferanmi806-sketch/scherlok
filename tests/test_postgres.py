"""Tests for the Postgres connector using mocks."""

from datetime import datetime
from unittest.mock import MagicMock, patch


def _make_connector_with_mock_cursor(rows: list[dict]) -> tuple[object, MagicMock]:
    """Build a PostgresConnector whose cursor returns the given rows."""
    from scherlok.connectors.postgres import PostgresConnector

    cur = MagicMock()
    cur.fetchall.return_value = rows
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cur

    c = PostgresConnector("postgresql://u:p@h/d")
    c._conn = conn
    return c, cur


def test_list_tables_query_includes_views():
    """Issue #7: list_tables must return both BASE TABLE and VIEW rows."""
    c, cur = _make_connector_with_mock_cursor(
        [
            {"table_name": "fct_orders"},  # BASE TABLE
            {"table_name": "stg_users"},  # VIEW
        ]
    )
    tables = c.list_tables()
    assert "stg_users" in tables
    assert "fct_orders" in tables

    # Query must filter to ('BASE TABLE', 'VIEW')
    sql = cur.execute.call_args.args[0]
    assert "'BASE TABLE'" in sql
    assert "'VIEW'" in sql


def test_get_column_max_uses_quoted_identifiers_and_one_aggregate():
    from psycopg2 import sql as pg_sql

    c, cur = _make_connector_with_mock_cursor([])
    latest = datetime(2026, 4, 20, 12, 0, 0)
    cur.fetchone.return_value = {"max_value": latest}

    result = c.get_column_max('events" archive', 'strange"updated_at')

    assert result == latest
    cur.execute.assert_called_once()
    query = cur.execute.call_args.args[0]
    assert isinstance(query, pg_sql.Composed)
    assert sum(isinstance(part, pg_sql.Identifier) for part in query._wrapped) == 2


@patch("scherlok.connectors.postgres.psycopg2.connect")
def test_connect_success(mock_connect):
    from scherlok.connectors.postgres import PostgresConnector

    mock_connect.return_value = MagicMock()
    c = PostgresConnector("postgresql://u:p@h/d")
    assert c.connect() is True


@patch("scherlok.connectors.postgres.psycopg2.connect")
def test_connect_failure(mock_connect):
    import psycopg2

    from scherlok.connectors.postgres import PostgresConnector

    mock_connect.side_effect = psycopg2.OperationalError("nope")
    c = PostgresConnector("postgresql://u:p@h/d")
    assert c.connect() is False

"""Table freshness profiling — last update detection."""

from datetime import date, datetime, time, timezone

from scherlok.connectors.base import BaseConnector

TIMESTAMP_COLUMN_PRIORITY = (
    "updated_at",
    "last_updated_at",
    "modified_at",
    "last_modified_at",
    "loaded_at",
    "ingested_at",
    "created_at",
)


def _timestamp_column_sort_key(column: dict) -> tuple[int, str, str] | None:
    """Return a stable priority key for plausible timestamp/date columns."""
    name = column.get("name")
    if not isinstance(name, str):
        return None

    column_type = str(column.get("type", "")).casefold().strip()
    if not (
        "timestamp" in column_type
        or "datetime" in column_type
        or column_type.startswith("date")
    ):
        return None

    normalized_name = name.casefold()
    try:
        priority = TIMESTAMP_COLUMN_PRIORITY.index(normalized_name)
    except ValueError:
        if normalized_name.endswith("_at"):
            priority = len(TIMESTAMP_COLUMN_PRIORITY)
        elif (
            normalized_name == "date"
            or normalized_name.startswith("date_")
            or normalized_name.endswith("_date")
        ):
            priority = len(TIMESTAMP_COLUMN_PRIORITY) + 1
        else:
            return None

    return priority, normalized_name, name


def _select_timestamp_column(columns: list[dict]) -> str | None:
    """Choose the highest-priority plausible timestamp/date column."""
    candidates = [
        (key, column["name"])
        for column in columns
        if (key := _timestamp_column_sort_key(column)) is not None
    ]
    return min(candidates)[1] if candidates else None


def _as_datetime(value: date | datetime) -> datetime:
    """Normalize a DATE result to midnight UTC for freshness arithmetic."""
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def profile_freshness(
    connector: BaseConnector,
    table: str,
    *,
    columns: list[dict] | None = None,
) -> dict:
    """Profile the freshness of a table.

    Returns:
        Dict with keys: last_modified (str ISO or None), hours_since_update (float or None),
        and freshness_source (metadata, a column name, or None).
    """
    last_mod = connector.get_last_modified(table)
    freshness_source = "metadata" if last_mod is not None else None

    if last_mod is None:
        available_columns = connector.get_columns(table) if columns is None else columns
        timestamp_column = _select_timestamp_column(available_columns)
        if timestamp_column is not None:
            last_mod = connector.get_column_max(table, timestamp_column)
            if last_mod is not None:
                freshness_source = timestamp_column

    hours_since: float | None = None

    if last_mod is not None:
        last_mod = _as_datetime(last_mod)
        if last_mod.tzinfo is None:
            last_mod = last_mod.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_mod
        hours_since = round(delta.total_seconds() / 3600, 2)

    return {
        "last_modified": last_mod.isoformat() if last_mod is not None else None,
        "hours_since_update": hours_since,
        "freshness_source": freshness_source,
    }

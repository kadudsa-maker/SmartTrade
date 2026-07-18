"""Pure helpers for the card-level FVG opportunity filter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


MATCHING_FVG_STATUSES = frozenset(("ACTIVE", "PENDING"))


def normalize_fvg_status(value: Any) -> str:
    value = getattr(value, "value", value)
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def record_has_qualifying_fvg(record: Mapping[str, Any] | None) -> bool:
    if not isinstance(record, Mapping):
        return False
    return (
        normalize_fvg_status(record.get("fvg_status")) in MATCHING_FVG_STATUSES
        and record.get("fvg_result") is not None
        and record.get("selected_fvg") is not None
    )


def record_matches_fvg_filter(record: Mapping[str, Any] | None, enabled: bool) -> bool:
    """Legacy pure helper retained for external callers."""
    return True if not enabled else record_has_qualifying_fvg(record)

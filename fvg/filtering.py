"""Pure helpers for the card-level FVG opportunity filter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


MATCHING_FVG_STATUSES = frozenset(("ACTIVE", "PENDING"))
FVG_ANALYSIS_DEFAULT = False
FVG_ONLY_DEFAULT = False


def normalize_fvg_status(value: Any) -> str:
    value = getattr(value, "value", value)
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def record_matches_fvg_filter(record: Mapping[str, Any] | None, enabled: bool) -> bool:
    if not enabled:
        return True
    if not isinstance(record, Mapping):
        return False
    return (
        normalize_fvg_status(record.get("fvg_status")) in MATCHING_FVG_STATUSES
        and record.get("fvg_result") is not None
        and record.get("selected_fvg") is not None
    )

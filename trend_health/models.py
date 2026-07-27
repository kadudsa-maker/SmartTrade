from dataclasses import dataclass
from enum import Enum


class TrendHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    WEAKENING = "WEAKENING"
    BREAKING = "BREAKING"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class TrendHealthResult:
    state: TrendHealthState
    reason: str
    protected_level: float | None = None
    protected_pivot_index: int | None = None

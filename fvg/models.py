from dataclasses import dataclass
from enum import Enum


class FVGDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FVGOpportunityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    NONE = ""


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class FairValueGap:
    direction: FVGDirection
    candle1_time: int
    candle3_time: int
    lower_price: float
    upper_price: float


@dataclass(frozen=True)
class EvaluatedFVG:
    gap: FairValueGap
    status: FVGOpportunityStatus
    distance_percent: float | None


@dataclass(frozen=True)
class FVGScanResult:
    current_price: float
    gaps: tuple[EvaluatedFVG, ...]
    selected_fvg: EvaluatedFVG | None
    status: FVGOpportunityStatus

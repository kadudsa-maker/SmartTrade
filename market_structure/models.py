from dataclasses import dataclass
from enum import Enum


class MarketStructureState(str, Enum):
    UPTREND = "UPTREND"
    POTENTIAL_DISTRIBUTION = "POTENTIAL_DISTRIBUTION"
    DOWNTREND_CONFIRMED = "DOWNTREND_CONFIRMED"
    DOWNTREND = "DOWNTREND"
    POTENTIAL_ACCUMULATION = "POTENTIAL_ACCUMULATION"
    UPTREND_CONFIRMED = "UPTREND_CONFIRMED"
    UNDEFINED = "UNDEFINED"


class PivotType(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


class DivergenceDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class TrendDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"


class Strength(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PriceStructure(str, Enum):
    HIGHER_HIGH_HIGHER_LOW = "HH_HL"
    LOWER_HIGH_LOWER_LOW = "LH_LL"
    FIRST_LOWER_HIGH = "FIRST_LH"
    FIRST_HIGHER_LOW = "FIRST_HL"
    BREAKDOWN_CONFIRMED = "BREAKDOWN_CONFIRMED"
    BREAKOUT_CONFIRMED = "BREAKOUT_CONFIRMED"
    MIXED = "MIXED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SemanticColor(str, Enum):
    POSITIVE = "positive"
    WARNING = "warning"
    NEGATIVE = "negative"
    ACCUMULATION = "accumulation"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class PricePivot:
    index: int
    price: float
    type: PivotType


@dataclass(frozen=True)
class MarketStructureResult:
    state: MarketStructureState
    previous_trend: TrendDirection
    strength: Strength
    reason: str
    price_structure: PriceStructure
    divergence_direction: DivergenceDirection | None
    rsi_value: float | None
    color_key: SemanticColor
    protected_level: float | None = None
    protected_pivot_index: int | None = None

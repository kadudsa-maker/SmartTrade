"""Pure domain models and evaluation for market structure."""

from .adapter import merge_price_pivots, normalize_price_pivots
from .config import (
    MARKET_STRUCTURE_PIVOT_WINDOW,
    get_market_structure_pivot_window,
)
from .evaluator import evaluate_market_structure
from .models import (
    DivergenceDirection,
    MarketStructureResult,
    MarketStructureState,
    PivotType,
    PricePivot,
    PriceStructure,
    SemanticColor,
    Strength,
    TrendDirection,
)

__all__ = [
    "DivergenceDirection",
    "MarketStructureResult",
    "MarketStructureState",
    "MARKET_STRUCTURE_PIVOT_WINDOW",
    "PivotType",
    "PricePivot",
    "PriceStructure",
    "SemanticColor",
    "Strength",
    "TrendDirection",
    "evaluate_market_structure",
    "get_market_structure_pivot_window",
    "merge_price_pivots",
    "normalize_price_pivots",
]

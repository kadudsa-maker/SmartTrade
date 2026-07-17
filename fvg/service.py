from typing import Sequence

from .detector import FVGDetector
from .evaluator import FVGEvaluator
from .models import Candle, FVGOpportunityStatus, FVGScanResult
from .selector import FVGSelector


class FVGService:
    """Run the stateless FVG detection and opportunity pipeline."""

    def analyze(
        self,
        closed_candles: Sequence[Candle],
        current_candle: Candle,
        previous_candle: Candle,
        pending_distance_percent: float = 0.30,
    ) -> FVGScanResult:
        gaps = FVGDetector.detect(closed_candles)
        evaluated_gaps = FVGEvaluator.evaluate(
            gaps,
            current_candle,
            previous_candle,
            pending_distance_percent,
        )
        selected_fvg = FVGSelector.select(
            evaluated_gaps,
            current_candle,
        )
        status = (
            selected_fvg.status
            if selected_fvg is not None
            else FVGOpportunityStatus.NONE
        )
        return FVGScanResult(
            current_price=float(current_candle.close),
            gaps=tuple(evaluated_gaps),
            selected_fvg=selected_fvg,
            status=status,
        )

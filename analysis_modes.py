"""Central capabilities for the analysis mode selected in the existing menu."""

from dataclasses import dataclass


RSI_VIEW_OFF = "RSI OFF"
RSI_VIEW_ON = "RSI ON"
RSI_VIEW_SORT = "RSI Sort"
RSI_VIEW_QUALITY_SORT = "RSI + Quality Sort"
FVG_ON = "FVG ON"
FVG_ONLY = "FVG ONLY"
FVG_RSI = "FVG + RSI"

ANALYSIS_MODE_OPTIONS = (
    RSI_VIEW_ON,
    RSI_VIEW_OFF,
    RSI_VIEW_SORT,
    RSI_VIEW_QUALITY_SORT,
    FVG_ON,
    FVG_ONLY,
    FVG_RSI,
)


@dataclass(frozen=True)
class AnalysisCapabilities:
    analyze_fvg: bool
    analyze_rsi: bool
    analyze_divergence: bool
    analyze_quality: bool
    require_fvg: bool = False
    require_good_rsi: bool = False
    sort_profile: str = "standard"


STANDARD_CAPABILITIES = AnalysisCapabilities(
    analyze_fvg=False,
    analyze_rsi=True,
    analyze_divergence=True,
    analyze_quality=True,
)

MODE_CAPABILITIES = {
    FVG_ON: AnalysisCapabilities(
        analyze_fvg=True,
        analyze_rsi=True,
        analyze_divergence=True,
        analyze_quality=True,
        sort_profile="fvg_rsi_quality",
    ),
    FVG_ONLY: AnalysisCapabilities(
        analyze_fvg=True,
        analyze_rsi=False,
        analyze_divergence=False,
        analyze_quality=False,
        require_fvg=True,
        sort_profile="fvg_only",
    ),
    FVG_RSI: AnalysisCapabilities(
        analyze_fvg=True,
        analyze_rsi=True,
        analyze_divergence=False,
        analyze_quality=False,
        sort_profile="fvg_rsi",
    ),
}


def capabilities_for_mode(mode):
    return MODE_CAPABILITIES.get(mode, STANDARD_CAPABILITIES)

from dataclasses import dataclass
from typing import Callable, Sequence

from .models import EvaluatedFVG, FVGDirection, FVGOpportunityStatus


FVG_CANVAS_TAG = "fvg-zone"
FVG_SHAPE_PREFIX = "FVG:"


@dataclass(frozen=True)
class FVGRenderStyle:
    fill_color: str
    line_color: str
    opacity: float
    line_width: float
    dash: str
    stipple: str


@dataclass(frozen=True)
class FVGRenderZone:
    key: str
    label: str
    direction: FVGDirection
    status: FVGOpportunityStatus
    x0: int
    x1: int
    y0: float
    y1: float
    style: FVGRenderStyle


class FVGChartOverlay:

    _BULLISH_COLOR = "#2ECC71"
    _BEARISH_COLOR = "#E74C3C"
    _STATUS_STYLE = {
        FVGOpportunityStatus.ACTIVE: (0.24, 2.0, "solid", "gray50"),
        FVGOpportunityStatus.PENDING: (0.15, 1.5, "dash", "gray25"),
        FVGOpportunityStatus.NONE: (0.08, 0.5, "dot", "gray12"),
    }

    @classmethod
    def zone_key(cls, evaluated_fvg):

        gap = evaluated_fvg.gap
        return (
            f"{FVG_SHAPE_PREFIX}{gap.direction.value}:"
            f"{gap.candle1_time}:{gap.candle3_time}:"
            f"{gap.lower_price}:{gap.upper_price}"
        )

    @classmethod
    def build_zones(cls, gaps: Sequence[EvaluatedFVG], right_edge: int):

        zones = []
        for evaluated_fvg in gaps:
            gap = evaluated_fvg.gap
            color = (
                cls._BULLISH_COLOR
                if gap.direction is FVGDirection.BULLISH
                else cls._BEARISH_COLOR
            )
            opacity, line_width, dash, stipple = cls._STATUS_STYLE[
                evaluated_fvg.status
            ]
            status_text = evaluated_fvg.status.value or "NONE"
            direction_text = gap.direction.value.upper()
            zones.append(
                FVGRenderZone(
                    key=cls.zone_key(evaluated_fvg),
                    label=f"FVG {status_text} {direction_text}",
                    direction=gap.direction,
                    status=evaluated_fvg.status,
                    x0=gap.candle3_time,
                    x1=int(right_edge),
                    y0=gap.lower_price,
                    y1=gap.upper_price,
                    style=FVGRenderStyle(
                        fill_color=color,
                        line_color=color,
                        opacity=opacity,
                        line_width=line_width,
                        dash=dash,
                        stipple=stipple,
                    ),
                )
            )
        return tuple(zones)

    @classmethod
    def clear_plotly_shapes(cls, figure):

        remaining = [
            shape
            for shape in (figure.layout.shapes or ())
            if not str(getattr(shape, "name", "")).startswith(FVG_SHAPE_PREFIX)
        ]
        figure.layout.shapes = tuple(remaining)

    @classmethod
    def add_plotly_shapes(
        cls,
        figure,
        gaps: Sequence[EvaluatedFVG],
        right_edge: int,
        time_converter: Callable[[int], object] = lambda value: value,
    ):

        cls.clear_plotly_shapes(figure)
        zones = cls.build_zones(gaps, right_edge)
        for zone in zones:
            figure.add_shape(
                type="rect",
                name=zone.key,
                xref="x",
                yref="y",
                x0=time_converter(zone.x0),
                x1=time_converter(zone.x1),
                y0=zone.y0,
                y1=zone.y1,
                fillcolor=zone.style.fill_color,
                opacity=zone.style.opacity,
                line=dict(
                    color=zone.style.line_color,
                    width=zone.style.line_width,
                    dash=zone.style.dash,
                ),
                layer="below",
            )
        return zones

    @classmethod
    def clear_canvas(cls, canvas):

        canvas.delete(FVG_CANVAS_TAG)

    @classmethod
    def draw_canvas_rectangles(
        cls,
        canvas,
        gaps: Sequence[EvaluatedFVG],
        right_edge: int,
        time_to_x: Callable[[int], float],
        price_to_y: Callable[[float], float],
        panel_bounds: tuple[float, float, float, float],
        right_edge_x: float | None = None,
    ):

        cls.clear_canvas(canvas)
        zones = cls.build_zones(gaps, right_edge)
        left, top, right, bottom = panel_bounds

        for zone in zones:
            raw_x0 = time_to_x(zone.x0)
            raw_x1 = time_to_x(zone.x1) if right_edge_x is None else right_edge_x
            raw_y0 = price_to_y(zone.y0)
            raw_y1 = price_to_y(zone.y1)

            x0 = max(left, min(right, min(raw_x0, raw_x1)))
            x1 = max(left, min(right, max(raw_x0, raw_x1)))
            y0 = max(top, min(bottom, min(raw_y0, raw_y1)))
            y1 = max(top, min(bottom, max(raw_y0, raw_y1)))
            if x1 <= left or x0 >= right or y1 <= top or y0 >= bottom:
                continue

            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=zone.style.fill_color,
                outline=zone.style.line_color,
                width=zone.style.line_width,
                dash=None if zone.style.dash == "solid" else (4, 3),
                stipple=zone.style.stipple,
                tags=(FVG_CANVAS_TAG, zone.key, zone.label),
            )
        return zones

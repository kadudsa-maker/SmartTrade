import inspect

import plotly.graph_objects as go
import pytest

from chart import SmartTradeChart
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
)
from fvg.chart_overlay import FVG_CANVAS_TAG, FVGChartOverlay


def evaluated(
    direction=FVGDirection.BULLISH,
    status=FVGOpportunityStatus.NONE,
    candle1_time=10,
    candle3_time=30,
    lower=100.0,
    upper=105.0,
    distance=None,
):
    return EvaluatedFVG(
        gap=FairValueGap(
            direction=direction,
            candle1_time=candle1_time,
            candle3_time=candle3_time,
            lower_price=lower,
            upper_price=upper,
        ),
        status=status,
        distance_percent=distance,
    )


class FakeCanvas:

    def __init__(self):
        self.rectangles = []
        self.other_items = ["candle", "divergence"]
        self.deleted = []

    def delete(self, tag):
        self.deleted.append(tag)
        if tag == FVG_CANVAS_TAG:
            self.rectangles = [
                item for item in self.rectangles
                if FVG_CANVAS_TAG not in item[4].get("tags", ())
            ]

    def create_rectangle(self, x0, y0, x1, y1, **options):
        self.rectangles.append((x0, y0, x1, y1, options))
        return len(self.rectangles)


def draw_canvas(gaps):
    canvas = FakeCanvas()
    zones = FVGChartOverlay.draw_canvas_rectangles(
        canvas,
        gaps,
        right_edge=80,
        time_to_x=lambda value: value,
        price_to_y=lambda value: 200 - value,
        panel_bounds=(0, 0, 100, 200),
        right_edge_x=100,
    )
    return canvas, zones


def test_bullish_fvg_builds_one_zone():
    assert len(FVGChartOverlay.build_zones([evaluated()], 80)) == 1


def test_bearish_fvg_builds_one_zone():
    assert len(FVGChartOverlay.build_zones([
        evaluated(direction=FVGDirection.BEARISH)
    ], 80)) == 1


def test_zone_x0_is_candle3_time():
    zone = FVGChartOverlay.build_zones([evaluated(candle3_time=33)], 80)[0]
    assert zone.x0 == 33


def test_zone_x0_is_not_candle1_time():
    zone = FVGChartOverlay.build_zones([
        evaluated(candle1_time=11, candle3_time=33)
    ], 80)[0]
    assert zone.x0 != 11


def test_zone_x1_is_chart_right_edge():
    zone = FVGChartOverlay.build_zones([evaluated()], 88)[0]
    assert zone.x1 == 88


def test_zone_y0_is_lower_price():
    zone = FVGChartOverlay.build_zones([evaluated(lower=0.9)], 80)[0]
    assert zone.y0 == 0.9


def test_zone_y1_is_upper_price():
    zone = FVGChartOverlay.build_zones([evaluated(upper=1.1)], 80)[0]
    assert zone.y1 == 1.1


def test_very_narrow_zone_keeps_exact_geometry():
    zone = FVGChartOverlay.build_zones([
        evaluated(lower=1.000001, upper=1.000002)
    ], 80)[0]
    assert zone.y1 - zone.y0 == pytest.approx(0.000001)


def test_very_low_price_keeps_exact_geometry():
    zone = FVGChartOverlay.build_zones([
        evaluated(lower=0.00001234, upper=0.00001299)
    ], 80)[0]
    assert (zone.y0, zone.y1) == (0.00001234, 0.00001299)


def test_many_gaps_build_many_separate_zones():
    zones = FVGChartOverlay.build_zones([
        evaluated(candle3_time=30),
        evaluated(candle3_time=40),
        evaluated(candle3_time=50),
    ], 80)
    assert len(zones) == 3
    assert len({zone.key for zone in zones}) == 3


def test_overlapping_gaps_are_not_merged():
    zones = FVGChartOverlay.build_zones([
        evaluated(lower=100, upper=110),
        evaluated(candle3_time=40, lower=105, upper=115),
    ], 80)
    assert [(zone.y0, zone.y1) for zone in zones] == [(100, 110), (105, 115)]


def test_input_order_does_not_change_zone_geometry():
    first = evaluated(candle3_time=30, lower=100, upper=105)
    second = evaluated(candle3_time=40, lower=110, upper=115)
    forward = FVGChartOverlay.build_zones([first, second], 80)
    reverse = FVGChartOverlay.build_zones([second, first], 80)
    geometry = lambda zones: sorted((z.x0, z.x1, z.y0, z.y1) for z in zones)
    assert geometry(forward) == geometry(reverse)


def test_bullish_uses_bullish_style():
    zone = FVGChartOverlay.build_zones([evaluated()], 80)[0]
    assert zone.style.fill_color == "#2ECC71"
    assert "BULLISH" in zone.label


def test_bearish_uses_bearish_style():
    zone = FVGChartOverlay.build_zones([
        evaluated(direction=FVGDirection.BEARISH)
    ], 80)[0]
    assert zone.style.fill_color == "#E74C3C"
    assert "BEARISH" in zone.label


def test_active_has_strongest_style():
    styles = {
        status: FVGChartOverlay.build_zones([evaluated(status=status)], 80)[0].style
        for status in FVGOpportunityStatus
    }
    assert styles[FVGOpportunityStatus.ACTIVE].opacity > styles[FVGOpportunityStatus.PENDING].opacity
    assert styles[FVGOpportunityStatus.ACTIVE].line_width > styles[FVGOpportunityStatus.PENDING].line_width


def test_pending_is_weaker_than_active():
    active = FVGChartOverlay.build_zones([
        evaluated(status=FVGOpportunityStatus.ACTIVE)
    ], 80)[0]
    pending = FVGChartOverlay.build_zones([
        evaluated(status=FVGOpportunityStatus.PENDING)
    ], 80)[0]
    assert pending.style.opacity < active.style.opacity
    assert pending.style.dash == "dash"


def test_none_is_most_subtle():
    none = FVGChartOverlay.build_zones([evaluated()], 80)[0]
    pending = FVGChartOverlay.build_zones([
        evaluated(status=FVGOpportunityStatus.PENDING)
    ], 80)[0]
    assert none.style.opacity < pending.style.opacity
    assert none.style.line_width < pending.style.line_width


def test_status_change_does_not_change_geometry():
    zones = [
        FVGChartOverlay.build_zones([evaluated(status=status)], 80)[0]
        for status in FVGOpportunityStatus
    ]
    assert len({(z.x0, z.x1, z.y0, z.y1) for z in zones}) == 1


@pytest.mark.parametrize("status", list(FVGOpportunityStatus))
def test_all_status_opacities_are_transparent(status):
    opacity = FVGChartOverlay.build_zones([
        evaluated(status=status)
    ], 80)[0].style.opacity
    assert 0 < opacity < 1


def test_status_and_direction_are_available_as_text_metadata():
    zone = FVGChartOverlay.build_zones([
        evaluated(
            direction=FVGDirection.BEARISH,
            status=FVGOpportunityStatus.PENDING,
        )
    ], 80)[0]
    assert zone.label == "FVG PENDING BEARISH"


def test_plotly_shape_targets_price_axes_only():
    figure = go.Figure()
    FVGChartOverlay.add_plotly_shapes(figure, [evaluated()], 80)
    shape = figure.layout.shapes[0]
    assert shape.xref == "x"
    assert shape.yref == "y"
    assert shape.yref != "y2"


def test_plotly_shape_is_below_traces():
    figure = go.Figure()
    FVGChartOverlay.add_plotly_shapes(figure, [evaluated()], 80)
    assert figure.layout.shapes[0].layer == "below"


def test_no_fvg_preserves_existing_rsi_shape_and_axis():
    figure = go.Figure()
    figure.update_layout(yaxis2=dict(range=[0, 100]))
    figure.add_shape(type="line", name="RSI level", yref="y2", y0=30, y1=30)
    before_range = tuple(figure.layout.yaxis2.range)
    FVGChartOverlay.add_plotly_shapes(figure, [], 80)
    assert len(figure.layout.shapes) == 1
    assert tuple(figure.layout.yaxis2.range) == before_range


def test_fvg_does_not_change_rsi_range():
    figure = go.Figure()
    figure.update_layout(yaxis2=dict(range=[0, 100]))
    FVGChartOverlay.add_plotly_shapes(figure, [evaluated()], 80)
    assert tuple(figure.layout.yaxis2.range) == (0, 100)


def test_clearing_plotly_fvg_preserves_marker_traces():
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=[1], y=[2], mode="markers", name="Pivot"))
    FVGChartOverlay.add_plotly_shapes(figure, [evaluated()], 80)
    FVGChartOverlay.clear_plotly_shapes(figure)
    assert len(figure.data) == 1
    assert figure.data[0].name == "Pivot"


def test_clearing_plotly_fvg_preserves_divergence_and_rsi_shapes():
    figure = go.Figure()
    figure.add_shape(type="line", name="Divergence", x0=1, x1=2, y0=1, y1=2)
    figure.add_shape(type="line", name="RSI level", yref="y2", y0=30, y1=30)
    FVGChartOverlay.add_plotly_shapes(figure, [evaluated()], 80)
    FVGChartOverlay.clear_plotly_shapes(figure)
    assert [shape.name for shape in figure.layout.shapes] == ["Divergence", "RSI level"]


def test_canvas_rectangle_is_clipped_to_price_panel():
    canvas = FakeCanvas()
    FVGChartOverlay.draw_canvas_rectangles(
        canvas,
        [evaluated(lower=0, upper=300)],
        80,
        time_to_x=lambda value: value,
        price_to_y=lambda value: 250 - value,
        panel_bounds=(0, 20, 100, 180),
        right_edge_x=100,
    )
    x0, y0, x1, y1, _options = canvas.rectangles[0]
    assert 0 <= x0 <= x1 <= 100
    assert 20 <= y0 <= y1 <= 180


def test_canvas_rectangle_has_stable_fvg_tags():
    canvas, _zones = draw_canvas([evaluated(status=FVGOpportunityStatus.ACTIVE)])
    tags = canvas.rectangles[0][4]["tags"]
    assert FVG_CANVAS_TAG in tags
    assert "FVG ACTIVE BULLISH" in tags


def test_canvas_draws_one_rectangle_per_overlapping_gap():
    canvas, _zones = draw_canvas([
        evaluated(lower=100, upper=110),
        evaluated(candle3_time=40, lower=105, upper=115),
    ])
    assert len(canvas.rectangles) == 2


def test_canvas_refresh_replaces_fvg_rectangles_without_duplicates():
    canvas, _zones = draw_canvas([evaluated()])
    FVGChartOverlay.draw_canvas_rectangles(
        canvas,
        [evaluated(candle3_time=40)],
        80,
        time_to_x=lambda value: value,
        price_to_y=lambda value: 200 - value,
        panel_bounds=(0, 0, 100, 200),
        right_edge_x=100,
    )
    assert len(canvas.rectangles) == 1
    assert canvas.rectangles[0][0] == 40


def test_canvas_clear_does_not_remove_candles_or_divergence():
    canvas, _zones = draw_canvas([evaluated()])
    FVGChartOverlay.clear_canvas(canvas)
    assert canvas.rectangles == []
    assert canvas.other_items == ["candle", "divergence"]


def test_chart_draws_fvg_before_candles_and_divergence():
    source = inspect.getsource(SmartTradeChart._draw)
    assert source.index("self._draw_fvg_zones(") < source.index("for index, candle")
    assert source.index("self._draw_fvg_zones(") < source.index("self._draw_regular_divergences(")

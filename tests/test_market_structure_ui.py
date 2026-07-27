import pytest

from analysis_modes import (
    ANALYSIS_MODE_OPTIONS,
    FVG_ON,
    FVG_ONLY,
    FVG_RSI,
    MARKET_STRUCTURE,
    RSI_VIEW_OFF,
    RSI_VIEW_ON,
    RSI_VIEW_QUALITY_SORT,
    RSI_VIEW_SORT,
    capabilities_for_mode,
)
from market_structure import (
    MarketStructureResult,
    MarketStructureState,
    PriceStructure,
    SemanticColor,
    Strength,
    TrendDirection,
)
from ui import (
    CARD_HEIGHT,
    GRAY,
    GREEN,
    MARKET_STRUCTURE_CARD_HEIGHT,
    MARKET_STRUCTURE_SEMANTIC_COLORS,
    MARKET_STRUCTURE_STATE_SEMANTICS,
    MARKET_STRUCTURE_STATE_TEXT,
    ORANGE,
    RED,
    TEXT_COLOR,
    TREND_HEALTH_STATE_SEMANTICS,
    TREND_HEALTH_STATE_TEXT,
    YELLOW,
    SmartTradeUI,
)
from trend_health import TrendHealthResult, TrendHealthState


class ModeValue:

    def __init__(self, value):

        self.value = value

    def get(self):

        return self.value

    def set(self, value):

        self.value = value


class FakeWidget:

    def __init__(
        self,
        *_args,
        text="",
        text_color="",
        mapped=False,
        **options,
    ):

        self.options = {
            "text": text,
            "text_color": text_color,
            **options,
        }
        self.mapped = mapped
        self.grid_calls = 0
        self.grid_remove_calls = 0
        self.grid_options = {}

    def cget(self, option):

        return self.options.get(option)

    def configure(self, **options):

        self.options.update(options)

    def winfo_exists(self):

        return True

    def winfo_ismapped(self):

        return self.mapped

    def grid(self, **options):

        self.mapped = True
        self.grid_calls += 1
        self.grid_options = options

    def grid_remove(self):

        self.mapped = False
        self.grid_remove_calls += 1


class FakeFrame(FakeWidget):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.column_options = {}

    def grid_columnconfigure(self, column, **options):

        self.column_options.setdefault(column, {}).update(options)


def _ui(mode=MARKET_STRUCTURE):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = ModeValue(mode)
    return ui


def _card(mapped=False):

    standard_cells = {
        name: FakeWidget(mapped=True)
        for name in ("setup", "quality", "age", "status")
    }
    return {
        "frame": FakeFrame(),
        "analysis_cells": standard_cells,
        "rsi_cell": FakeWidget(mapped=True),
        "fvg_cell": FakeWidget(mapped=True),
        "fvg_header": FakeWidget(text="old FVG"),
        "fvg_detail": FakeWidget(text="old detail"),
        "market_structure_cell": FakeWidget(mapped=mapped),
        "market_structure_status": FakeWidget(),
        "market_structure_reason": FakeWidget(),
        "trend_health_status": FakeWidget(),
        "trend_health_reason": FakeWidget(),
        "market_structure_rsi_title": FakeWidget(text="RSI", mapped=True),
        "market_structure_rsi": FakeWidget(),
        "market_structure_quality_title": FakeWidget(
            text="Quality",
            mapped=True,
        ),
        "market_structure_quality": FakeWidget(),
    }


def _result(state, reason=""):

    return MarketStructureResult(
        state=state,
        previous_trend=TrendDirection.NONE,
        strength=Strength.MEDIUM,
        reason=reason,
        price_structure=PriceStructure.MIXED,
        divergence_direction=None,
        rsi_value=None,
        color_key=MARKET_STRUCTURE_STATE_SEMANTICS[state],
    )


def _health(state, reason=""):

    return TrendHealthResult(state=state, reason=reason)


def test_market_structure_mode_exists_as_an_independent_option():

    assert MARKET_STRUCTURE == "Market Structure"
    assert MARKET_STRUCTURE in ANALYSIS_MODE_OPTIONS
    capabilities = capabilities_for_mode(MARKET_STRUCTURE)
    assert capabilities.analyze_market_structure is True
    assert capabilities.analyze_fvg is False
    assert capabilities.analyze_rsi is False
    assert capabilities.analyze_divergence is False
    assert capabilities.analyze_quality is False


def test_existing_analysis_mode_capabilities_are_unchanged():

    expected = {
        RSI_VIEW_ON: (False, True, True, True),
        RSI_VIEW_OFF: (False, True, True, True),
        RSI_VIEW_SORT: (False, True, True, True),
        RSI_VIEW_QUALITY_SORT: (False, True, True, True),
        FVG_ON: (True, True, True, True),
        FVG_ONLY: (True, False, False, False),
        FVG_RSI: (True, True, False, False),
    }

    for mode, values in expected.items():
        capabilities = capabilities_for_mode(mode)
        assert (
            capabilities.analyze_fvg,
            capabilities.analyze_rsi,
            capabilities.analyze_divergence,
            capabilities.analyze_quality,
        ) == values


@pytest.mark.parametrize(
    "state, expected",
    [
        (MarketStructureState.UPTREND, "Uptrend"),
        (
            MarketStructureState.POTENTIAL_DISTRIBUTION,
            "Potential Distribution",
        ),
        (MarketStructureState.DOWNTREND_CONFIRMED, "Downtrend Confirmed"),
        (MarketStructureState.DOWNTREND, "Downtrend"),
        (
            MarketStructureState.POTENTIAL_ACCUMULATION,
            "Potential Accumulation",
        ),
        (MarketStructureState.UPTREND_CONFIRMED, "Uptrend Confirmed"),
        (MarketStructureState.UNDEFINED, "Undefined"),
    ],
)
def test_every_state_has_explicit_ui_text(state, expected):

    assert MARKET_STRUCTURE_STATE_TEXT[state] == expected


@pytest.mark.parametrize(
    "state, semantic, color",
    [
        (MarketStructureState.UPTREND, SemanticColor.POSITIVE, GREEN),
        (
            MarketStructureState.POTENTIAL_DISTRIBUTION,
            SemanticColor.WARNING,
            YELLOW,
        ),
        (
            MarketStructureState.DOWNTREND_CONFIRMED,
            SemanticColor.NEGATIVE,
            RED,
        ),
        (MarketStructureState.DOWNTREND, SemanticColor.NEGATIVE, RED),
        (
            MarketStructureState.POTENTIAL_ACCUMULATION,
            SemanticColor.ACCUMULATION,
            ORANGE,
        ),
        (
            MarketStructureState.UPTREND_CONFIRMED,
            SemanticColor.POSITIVE,
            GREEN,
        ),
        (MarketStructureState.UNDEFINED, SemanticColor.NEUTRAL, GRAY),
    ],
)
def test_every_state_has_explicit_semantic_color(state, semantic, color):

    assert MARKET_STRUCTURE_STATE_SEMANTICS[state] is semantic
    assert MARKET_STRUCTURE_SEMANTIC_COLORS[semantic] == color


@pytest.mark.parametrize(
    "state, text, semantic, color",
    [
        (TrendHealthState.HEALTHY, "Healthy", SemanticColor.POSITIVE, GREEN),
        (
            TrendHealthState.WEAKENING,
            "Weakening",
            SemanticColor.WARNING,
            YELLOW,
        ),
        (TrendHealthState.BREAKING, "Breaking", SemanticColor.NEGATIVE, RED),
        (TrendHealthState.UNDEFINED, "Undefined", SemanticColor.NEUTRAL, GRAY),
    ],
)
def test_every_trend_health_state_has_ui_text_and_semantic_color(
    state,
    text,
    semantic,
    color,
):

    assert TREND_HEALTH_STATE_TEXT[state] == text
    assert TREND_HEALTH_STATE_SEMANTICS[state] is semantic
    assert MARKET_STRUCTURE_SEMANTIC_COLORS[semantic] == color


def test_card_shows_state_and_reason_in_market_structure_mode():

    ui = _ui()
    card = _card()

    assert ui.update_market_structure_card_section(
        card,
        _result(
            MarketStructureState.POTENTIAL_DISTRIBUTION,
            "Bearish divergence after uptrend",
        ),
    )
    assert card["market_structure_cell"].mapped is True
    assert card["market_structure_status"].cget("text") == "Potential Distribution"
    assert card["market_structure_status"].cget("text_color") == YELLOW
    assert (
        card["market_structure_reason"].cget("text")
        == "Bearish divergence after uptrend"
    )
    assert card["market_structure_reason"].mapped is True


def test_missing_reason_is_cleared_and_hidden():

    ui = _ui()
    card = _card()
    card["market_structure_reason"].configure(text="old reason")
    card["market_structure_reason"].mapped = True

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND, None),
    )

    assert card["market_structure_reason"].cget("text") == ""
    assert card["market_structure_reason"].mapped is False


def test_undefined_and_missing_result_use_neutral_fallback():

    ui = _ui()

    for value in (_result(MarketStructureState.UNDEFINED), None):
        card = _card()
        assert ui.update_market_structure_card_section(card, value)
        assert card["market_structure_status"].cget("text") == "Undefined"
        assert card["market_structure_status"].cget("text_color") == GRAY
        assert card["market_structure_reason"].cget("text") == ""


def test_existing_widgets_update_state_color_and_reason_without_duplication():

    ui = _ui()
    card = _card()
    widget_ids = tuple(id(widget) for widget in card.values())

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND, "HH + HL sequence"),
    )
    ui.update_market_structure_card_section(
        card,
        _result(
            MarketStructureState.POTENTIAL_DISTRIBUTION,
            "Bearish divergence after uptrend",
        ),
    )

    assert tuple(id(widget) for widget in card.values()) == widget_ids
    assert card["market_structure_status"].cget("text") == "Potential Distribution"
    assert card["market_structure_status"].cget("text_color") == YELLOW
    assert (
        card["market_structure_reason"].cget("text")
        == "Bearish divergence after uptrend"
    )


def test_trend_health_updates_text_color_and_reason_on_existing_widgets():

    ui = _ui()
    card = _card()
    health_widget_ids = (
        id(card["trend_health_status"]),
        id(card["trend_health_reason"]),
    )

    for state, reason, color in (
        (
            TrendHealthState.HEALTHY,
            "Structure intact, no active warning",
            GREEN,
        ),
        (
            TrendHealthState.WEAKENING,
            "Bearish divergence, protected HL intact",
            YELLOW,
        ),
        (
            TrendHealthState.BREAKING,
            "Close below protected HL",
            RED,
        ),
        (
            TrendHealthState.HEALTHY,
            "Structure intact, no active warning",
            GREEN,
        ),
    ):
        assert ui.update_market_structure_card_section(
            card,
            _result(MarketStructureState.UPTREND),
            trend_health=_health(state, reason),
        )
        assert card["trend_health_status"].cget("text") == state.value.title()
        assert card["trend_health_status"].cget("text_color") == color
        assert card["trend_health_reason"].cget("text") == reason

    assert health_widget_ids == (
        id(card["trend_health_status"]),
        id(card["trend_health_reason"]),
    )


def test_missing_trend_health_uses_safe_undefined_fallback():

    ui = _ui()
    card = _card()
    card["trend_health_status"].configure(text="Breaking", text_color=RED)
    card["trend_health_reason"].configure(text="old reason")
    card["trend_health_reason"].mapped = True

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND),
        trend_health=None,
    )

    assert card["trend_health_status"].cget("text") == "Undefined"
    assert card["trend_health_status"].cget("text_color") == GRAY
    assert card["trend_health_reason"].cget("text") == ""
    assert card["trend_health_reason"].mapped is False


def test_trend_health_color_does_not_change_market_structure_color():

    ui = _ui()
    card = _card()

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND),
        trend_health=_health(
            TrendHealthState.WEAKENING,
            "Bearish divergence, protected HL intact",
        ),
    )

    assert card["market_structure_status"].cget("text_color") == GREEN
    assert card["trend_health_status"].cget("text_color") == YELLOW


def test_mode_change_shows_and_hides_section_without_reserved_widget():

    ui = _ui(RSI_VIEW_ON)
    card = _card(mapped=False)

    ui.update_market_structure_card_visibility(card)
    assert card["market_structure_cell"].mapped is False

    ui.rsi_view_option.set(MARKET_STRUCTURE)
    ui.update_market_structure_card_visibility(card)
    assert card["market_structure_cell"].mapped is True

    ui.rsi_view_option.set(FVG_ON)
    ui.update_market_structure_card_visibility(card)
    assert card["market_structure_cell"].mapped is False


def test_market_structure_mode_uses_full_width_dedicated_layout():

    ui = _ui()
    card = _card(mapped=False)

    ui.update_card_analysis_visibility(card)
    ui.update_fvg_card_section(card)

    assert all(
        not cell.mapped
        for cell in card["analysis_cells"].values()
    )
    assert card["rsi_cell"].mapped is False
    assert card["fvg_cell"].mapped is False
    assert card["market_structure_cell"].mapped is True
    assert card["frame"].cget("height") == MARKET_STRUCTURE_CARD_HEIGHT
    assert MARKET_STRUCTURE_CARD_HEIGHT != 120
    assert CARD_HEIGHT <= MARKET_STRUCTURE_CARD_HEIGHT <= 76
    assert card["frame"].column_options[0] == {"weight": 0, "minsize": 88}
    assert card["frame"].column_options[6] == {"weight": 1}
    for column in (1, 2, 3, 4, 5):
        assert card["frame"].column_options[column]["minsize"] == 0


def test_hidden_parent_does_not_prevent_removing_legacy_widgets_from_grid():

    ui = _ui()
    card = _card(mapped=False)
    for cell in card["analysis_cells"].values():
        cell.mapped = False
    card["rsi_cell"].mapped = False

    ui.update_card_analysis_visibility(card)

    assert all(
        cell.grid_remove_calls == 1
        for cell in card["analysis_cells"].values()
    )
    assert card["rsi_cell"].grid_remove_calls == 1


def test_market_structure_panel_uses_separate_horizontal_columns(monkeypatch):

    monkeypatch.setattr("ui.ctk.CTkFrame", FakeFrame)
    monkeypatch.setattr("ui.ctk.CTkLabel", FakeWidget)
    ui = _ui()

    (
        cell,
        status,
        reason,
        trend_status,
        trend_reason,
        rsi_title,
        rsi,
        quality_title,
        quality,
    ) = ui.create_market_structure_card_section(FakeFrame())

    assert cell.grid_options["column"] == 1
    assert cell.grid_options["columnspan"] == 6
    assert status.grid_options["column"] == 0
    assert reason.grid_options["column"] == 0
    assert trend_status.grid_options["column"] == 1
    assert trend_reason.grid_options["column"] == 1
    assert rsi_title.grid_options["column"] == 2
    assert rsi.grid_options["column"] == 2
    assert quality_title.grid_options["column"] == 3
    assert quality.grid_options["column"] == 3
    assert rsi_title.cget("text") == "RSI"
    assert quality_title.cget("text") == "Quality"


@pytest.mark.parametrize(
    ("mode", "standard_visible", "rsi_visible"),
    [
        (RSI_VIEW_ON, True, True),
        (FVG_ON, True, True),
        (FVG_ONLY, False, False),
        (FVG_RSI, False, True),
    ],
)
def test_other_modes_keep_their_existing_card_layout(
    mode,
    standard_visible,
    rsi_visible,
):

    ui = _ui(mode)
    card = _card(mapped=True)

    ui.update_card_analysis_visibility(card)

    assert all(
        cell.mapped is standard_visible
        for cell in card["analysis_cells"].values()
    )
    assert card["rsi_cell"].mapped is rsi_visible
    assert card["market_structure_cell"].mapped is False
    assert card["frame"].cget("height") == CARD_HEIGHT
    assert card["frame"].column_options[0] == {"weight": 1, "minsize": 88}
    assert card["frame"].column_options[6] == {"weight": 0}


def test_mode_switch_restores_standard_cells_without_empty_columns():

    ui = _ui()
    card = _card(mapped=False)
    ui.update_card_analysis_visibility(card)

    ui.rsi_view_option.set(RSI_VIEW_ON)
    ui.update_card_analysis_visibility(card)

    assert all(cell.mapped for cell in card["analysis_cells"].values())
    assert card["rsi_cell"].mapped is True
    assert card["market_structure_cell"].mapped is False
    assert card["frame"].cget("height") == CARD_HEIGHT
    assert card["frame"].column_options[1]["minsize"] == 42
    assert card["frame"].column_options[2]["minsize"] == 46
    assert card["frame"].column_options[3]["minsize"] == 48
    assert card["frame"].column_options[4]["minsize"] == 74
    assert card["frame"].column_options[5]["minsize"] == 62

    ui.rsi_view_option.set(MARKET_STRUCTURE)
    ui.update_card_analysis_visibility(card)

    assert all(
        not cell.mapped
        for cell in card["analysis_cells"].values()
    )
    assert card["rsi_cell"].mapped is False
    assert card["market_structure_cell"].mapped is True


def test_dedicated_panel_shows_all_market_structure_content():

    ui = _ui()
    card = _card()

    ui.update_market_structure_card_section(
        card,
        _result(
            MarketStructureState.UPTREND,
            "HH + HL active sequence",
        ),
        trend_health=_health(
            TrendHealthState.HEALTHY,
            "Structure intact, no active warning",
        ),
        rsi=72.7,
        quality=91,
    )

    assert card["market_structure_cell"].mapped is True
    assert card["market_structure_status"].cget("text") == "Uptrend"
    assert card["market_structure_reason"].cget("text") == (
        "HH + HL active sequence"
    )
    assert card["trend_health_status"].cget("text") == "Healthy"
    assert card["trend_health_reason"].cget("text") == (
        "Structure intact, no active warning"
    )
    assert card["market_structure_rsi_title"].cget("text") == "RSI"
    assert card["market_structure_rsi"].cget("text") == "72.7"
    assert card["market_structure_quality_title"].cget("text") == "Quality"
    assert card["market_structure_quality"].cget("text") == "91"


def test_market_structure_context_shows_formatted_rsi_and_quality():

    ui = _ui()
    card = _card()

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.POTENTIAL_DISTRIBUTION),
        rsi=67.44,
        quality=91,
    )

    assert card["market_structure_rsi_title"].cget("text") == "RSI"
    assert card["market_structure_rsi"].cget("text") == "67.4"
    assert card["market_structure_quality_title"].cget("text") == "Quality"
    assert card["market_structure_quality"].cget("text") == "91"


def test_missing_context_values_show_dashes_without_none_or_null():

    ui = _ui()
    card = _card()

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND),
        rsi=None,
        quality=None,
    )

    texts = (
        card["market_structure_rsi"].cget("text"),
        card["market_structure_quality"].cget("text"),
    )
    assert texts == ("—", "—")
    assert all("None" not in text and "null" not in text for text in texts)


@pytest.mark.parametrize("missing_value", [False, "null", float("nan")])
def test_invalid_context_values_are_not_rendered(missing_value):

    ui = _ui()

    assert ui.format_market_structure_rsi(missing_value) == "—"
    assert ui.format_market_structure_quality(missing_value) == "—"


def test_context_values_remain_neutral_and_do_not_change_state_color():

    ui = _ui()
    card = _card()

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.DOWNTREND),
        rsi=95,
        quality=100,
    )

    assert card["market_structure_status"].cget("text_color") == RED
    assert card["market_structure_rsi"].cget("text_color") == TEXT_COLOR
    assert card["market_structure_quality"].cget("text_color") == TEXT_COLOR


def test_context_values_refresh_on_the_same_widgets():

    ui = _ui()
    card = _card()
    rsi_id = id(card["market_structure_rsi"])
    quality_id = id(card["market_structure_quality"])

    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND),
        rsi=42.8,
        quality=63,
    )
    ui.update_market_structure_card_section(
        card,
        _result(MarketStructureState.UPTREND),
        rsi=58.1,
        quality=91,
    )

    assert id(card["market_structure_rsi"]) == rsi_id
    assert id(card["market_structure_quality"]) == quality_id
    assert card["market_structure_rsi"].cget("text") == "58.1"
    assert card["market_structure_quality"].cget("text") == "91"


def test_context_values_do_not_change_market_structure_sort_key():

    ui = _ui()

    low_context = {"rsi": 10, "quality": 1, "divergence": None}
    high_context = {"rsi": 90, "quality": 100, "divergence": None}

    assert ui.analysis_mode_sort_key(low_context) == (0,)
    assert ui.analysis_mode_sort_key(high_context) == (0,)


def test_trend_health_does_not_change_market_structure_sort_or_filter_inputs():

    ui = _ui()
    healthy = {
        "market_structure": _result(MarketStructureState.UPTREND),
        "trend_health": _health(TrendHealthState.HEALTHY),
    }
    breaking = {
        "market_structure": _result(MarketStructureState.UPTREND),
        "trend_health": _health(TrendHealthState.BREAKING),
    }

    assert ui.analysis_mode_sort_key(healthy) == (0,)
    assert ui.analysis_mode_sort_key(breaking) == (0,)
    assert ui.market_structure_filter_state(
        healthy["market_structure"]
    ) is MarketStructureState.UPTREND
    assert ui.market_structure_filter_state(
        breaking["market_structure"]
    ) is MarketStructureState.UPTREND

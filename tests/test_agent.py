from __future__ import annotations

from agent import run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


def test_agent_complete_flow_populates_state():
    session = run_agent(
        "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers.",
        wardrobe=get_example_wardrobe(),
    )

    assert session["error"] is None
    assert session["selected_item"]["title"] == "Vintage Band Tee — Faded Grey"
    assert any("retry search_listings" in step for step in session["trace"])
    assert session["price_assessment"]["assessment"] in {"good deal", "fair", "pricey", "unknown"}
    assert session["outfit_suggestion"]
    assert session["fit_card"]
    assert any("search_listings" in step for step in session["trace"])
    assert any("compare_price" in step for step in session["trace"])
    assert any("get_trend_awareness" in step for step in session["trace"])
    assert any("suggest_outfit" in step for step in session["trace"])
    assert any("create_fit_card" in step for step in session["trace"])
    assert "Trend-aware note" in session["outfit_suggestion"]


def test_agent_no_results_stops_before_outfit():
    session = run_agent("designer ballgown under $5, size XXS", wardrobe=get_example_wardrobe())

    assert session["error"] is not None
    assert session["selected_item"] is None
    assert session["price_assessment"] is None
    assert session["trend_context"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert not any("compare_price" in step for step in session["trace"])
    assert not any("get_trend_awareness" in step for step in session["trace"])
    assert not any("suggest_outfit" in step for step in session["trace"])


def test_agent_empty_wardrobe_still_returns_fit_card():
    session = run_agent(
        "vintage graphic tee under $30 size M",
        wardrobe=get_empty_wardrobe(),
    )

    assert session["error"] is None
    assert session["outfit_suggestion"]
    assert session["fit_card"]

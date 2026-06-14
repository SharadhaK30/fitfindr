from __future__ import annotations

from tools import compare_price, create_fit_card, get_trend_awareness, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["title"] == "Vintage Band Tee — Faded Grey"


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)

    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_with_empty_wardrobe_returns_advice():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())

    assert isinstance(suggestion, str)
    assert "Start with" in suggestion
    assert "closet basics" in suggestion


def test_suggest_outfit_uses_wardrobe_piece():
    results = search_listings("vintage graphic tee", size=None, max_price=30)
    suggestion = suggest_outfit(results[0], get_example_wardrobe())

    assert "Baggy straight-leg jeans, dark wash" in suggestion


def test_create_fit_card_handles_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    caption = create_fit_card("", results[0])

    assert caption == "I need an outfit suggestion before I can write a fit card."


def test_create_fit_card_returns_caption():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    caption = create_fit_card("Pair it with baggy jeans and chunky sneakers.", results[0])

    assert isinstance(caption, str)
    assert len(caption) > 20


def test_compare_price_returns_reasoned_assessment():
    results = search_listings("vintage graphic tee", size=None, max_price=30)
    assessment = compare_price(results[0])

    assert assessment["assessment"] in {"good deal", "fair", "pricey", "unknown"}
    assert assessment["item_price"] == results[0]["price"]
    assert assessment["comparable_count"] > 0
    assert "average" in assessment["reasoning"]


def test_trend_awareness_returns_tags_and_tip():
    results = search_listings("vintage graphic tee", size=None, max_price=30)
    trend = get_trend_awareness(results[0], size=None)

    assert trend["trend_tags"]
    assert trend["styling_tip"]
    assert "mock recent resale tag snapshot" in trend["source"]

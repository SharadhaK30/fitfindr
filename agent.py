"""Planning loop and state management for FitFindr."""

from __future__ import annotations

import re
from typing import Any

from tools import compare_price, create_fit_card, get_trend_awareness, search_listings, suggest_outfit
from utils.data_loader import get_example_wardrobe


def _extract_max_price(query: str) -> float | None:
    price_language = re.search(
        r"(?:under|below|less than|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)",
        query,
        re.I,
    )
    if price_language:
        return float(price_language.group(1))

    dollar_amount = re.search(r"\$(\d+(?:\.\d+)?)", query)
    if dollar_amount:
        return float(dollar_amount.group(1))

    return None


def _extract_size(query: str) -> str | None:
    match = re.search(r"\bsize\s+([a-z0-9]+)\b", query, re.I)
    return match.group(1).upper() if match else None


def _clean_description(query: str) -> str:
    description = re.sub(r"\bsize\s+[a-z0-9]+\b", " ", query, flags=re.I)
    description = re.sub(r"(?:under|below|less than|up to|max(?:imum)?)\s*\$?\s*\d+(?:\.\d+)?", " ", description, flags=re.I)
    description = re.sub(r"\$\d+(?:\.\d+)?", " ", description)
    description = re.sub(r"\b(i mostly wear|my wardrobe has|i wear)\b.*", " ", description, flags=re.I)
    description = re.sub(r"[^a-zA-Z0-9'\s-]", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    return description or query.strip()


def _summarize_listing(item: dict[str, Any] | None) -> str | None:
    if not item:
        return None
    return (
        f"{item.get('title')} - ${float(item.get('price', 0)):.0f} on "
        f"{item.get('platform')} ({item.get('size')}, {item.get('condition')})"
    )


def run_agent(
    user_query: str,
    wardrobe: dict[str, Any] | None = None,
    size: str | None = None,
    max_price: float | None = None,
) -> dict[str, Any]:
    """Run FitFindr's conditional planning loop.

    The loop chooses the next tool from session state. It stops early when
    search returns no usable listing, which prevents downstream tools from
    receiving empty inputs.
    """
    session: dict[str, Any] = {
        "query": user_query,
        "search_params": {
            "description": _clean_description(user_query),
            "size": size or _extract_size(user_query),
            "max_price": max_price if max_price is not None else _extract_max_price(user_query),
        },
        "listings": [],
        "selected_item": None,
        "selected_item_summary": None,
        "price_assessment": None,
        "trend_context": None,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
        "trace": [],
    }
    active_wardrobe = wardrobe if wardrobe is not None else get_example_wardrobe()
    next_step: str | None = "search"

    while next_step:
        if next_step == "search":
            params = session["search_params"]
            session["trace"].append(f"search_listings({params})")
            results = search_listings(
                params["description"],
                size=params["size"],
                max_price=params["max_price"],
            )

            if not results and params["size"]:
                fallback_params = {**params, "size": None}
                session["trace"].append(f"retry search_listings({fallback_params})")
                results = search_listings(
                    fallback_params["description"],
                    size=None,
                    max_price=fallback_params["max_price"],
                )
                if results:
                    session["search_params"] = fallback_params
                    session["trace"].append("No exact size match; retried without the size filter.")

            session["listings"] = results
            if not results:
                session["error"] = (
                    "I could not find matching listings. Try a broader item "
                    "description, a higher max price, or leaving size blank."
                )
                session["trace"].append("stop: search returned no listings")
                next_step = None
            else:
                session["selected_item"] = results[0]
                session["selected_item_summary"] = _summarize_listing(results[0])
                session["trace"].append(f"selected_item={results[0].get('id')}")
                next_step = "price_check"

        elif next_step == "price_check":
            if not session["selected_item"]:
                session["error"] = "I need a selected listing before comparing price."
                session["trace"].append("stop: selected_item missing before price_check")
                next_step = None
                continue

            session["trace"].append("compare_price(selected_item)")
            session["price_assessment"] = compare_price(session["selected_item"])
            next_step = "trend_check"

        elif next_step == "trend_check":
            if not session["selected_item"]:
                session["error"] = "I need a selected listing before checking trends."
                session["trace"].append("stop: selected_item missing before trend_check")
                next_step = None
                continue

            session["trace"].append("get_trend_awareness(selected_item, size)")
            session["trend_context"] = get_trend_awareness(
                session["selected_item"],
                session["search_params"].get("size"),
            )
            next_step = "outfit"

        elif next_step == "outfit":
            if not session["selected_item"]:
                session["error"] = "I need a selected listing before styling an outfit."
                session["trace"].append("stop: selected_item missing")
                next_step = None
                continue

            session["trace"].append("suggest_outfit(selected_item, wardrobe)")
            outfit = suggest_outfit(session["selected_item"], active_wardrobe)
            if outfit and session.get("trend_context", {}).get("styling_tip"):
                outfit = f"{outfit} Trend-aware note: {session['trend_context']['styling_tip']}"
            session["outfit_suggestion"] = outfit
            if not outfit:
                session["error"] = "I could not build an outfit suggestion from this listing."
                session["trace"].append("stop: outfit suggestion empty")
                next_step = None
            else:
                next_step = "fit_card"

        elif next_step == "fit_card":
            session["trace"].append("create_fit_card(outfit_suggestion, selected_item)")
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"] or "",
                session["selected_item"],
            )
            next_step = None

        else:
            session["error"] = f"Unknown planning step: {next_step}"
            session["trace"].append("stop: unknown step")
            next_step = None

    return session


if __name__ == "__main__":
    examples = [
        "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers.",
        "designer ballgown under $5, size XXS",
    ]
    for query in examples:
        state = run_agent(query)
        print("\nQUERY:", query)
        print("TRACE:", " -> ".join(state["trace"]))
        print("ERROR:", state["error"])
        print("SELECTED:", state["selected_item_summary"])
        print("PRICE:", state["price_assessment"])
        print("OUTFIT:", state["outfit_suggestion"])
        print("FIT CARD:", state["fit_card"])

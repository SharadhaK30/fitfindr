"""Tool implementations for the FitFindr agent."""

from __future__ import annotations

import os
import random
import re
from typing import Any

from utils.data_loader import load_listings


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value).lower()
    return str(value).lower()


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", text.lower()) if len(token) > 1}


def _size_matches(item_size: Any, requested_size: str | None) -> bool:
    if not requested_size:
        return True
    return str(item_size).strip().lower() == requested_size.strip().lower()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict[str, Any]]:
    """Search mock secondhand listings.

    Args:
        description: Natural-language description of the desired item.
        size: Optional exact size filter such as "M", "L", "8", or "OS".
        max_price: Optional maximum price in dollars.

    Returns:
        A relevance-sorted list of listing dictionaries. Returns [] if no
        listings match or if the data cannot be loaded.
    """
    try:
        listings = load_listings()
    except (OSError, ValueError):
        return []

    query_tokens = _tokens(description)
    results: list[tuple[int, float, dict[str, Any]]] = []

    for item in listings:
        price = float(item.get("price", 0))
        if max_price is not None and price > float(max_price):
            continue
        if not _size_matches(item.get("size"), size):
            continue

        searchable = " ".join(
            [
                _normalize_text(item.get("title")),
                _normalize_text(item.get("description")),
                _normalize_text(item.get("category")),
                _normalize_text(item.get("style_tags")),
                _normalize_text(item.get("colors")),
                _normalize_text(item.get("brand")),
                _normalize_text(item.get("platform")),
            ]
        )
        listing_tokens = _tokens(searchable)
        overlap = query_tokens & listing_tokens

        score = len(overlap) * 4
        title = _normalize_text(item.get("title"))
        category = _normalize_text(item.get("category"))
        tags = _normalize_text(item.get("style_tags"))
        for token in query_tokens:
            if token in title:
                score += 3
            if token in category:
                score += 2
            if token in tags:
                score += 2

        if not query_tokens or score > 0:
            results.append((score, price, item))

    results.sort(key=lambda row: (-row[0], row[1], row[2].get("title", "")))
    return [item for _, _, item in results]


def _call_groq(prompt: str, temperature: float = 0.7) -> str | None:
    """Call Groq when configured; otherwise return None for local fallback."""
    if os.getenv("FITFINDR_USE_LLM", "1") == "0":
        return None

    try:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None

        from groq import Groq

        client = Groq(api_key=api_key, timeout=10.0)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are FitFindr, a concise secondhand styling "
                        "assistant. Give specific, wearable advice."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=180,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def _format_item(item: dict[str, Any]) -> str:
    return (
        f"{item.get('title', 'This item')} "
        f"({item.get('category', 'piece')}, {item.get('size', 'size unknown')}, "
        f"${float(item.get('price', 0)):.0f})"
    )


def compare_price(new_item: dict[str, Any]) -> dict[str, Any]:
    """Estimate whether a selected listing is fairly priced.

    Args:
        new_item: Listing dictionary selected by the agent.

    Returns:
        A dictionary with assessment, item_price, average_comparable_price,
        comparable_count, comparable_titles, and reasoning. If comparison is
        not possible, the dictionary contains assessment="unknown" plus a
        user-facing reasoning string.
    """
    if not new_item:
        return {
            "assessment": "unknown",
            "item_price": None,
            "average_comparable_price": None,
            "comparable_count": 0,
            "comparable_titles": [],
            "reasoning": "I need a selected listing before I can compare price.",
        }

    try:
        listings = load_listings()
    except (OSError, ValueError):
        return {
            "assessment": "unknown",
            "item_price": new_item.get("price"),
            "average_comparable_price": None,
            "comparable_count": 0,
            "comparable_titles": [],
            "reasoning": "I could not load comparable listings, so I cannot judge the price yet.",
        }

    item_tags = set(new_item.get("style_tags", []))
    item_category = new_item.get("category")
    item_id = new_item.get("id")
    comparables: list[dict[str, Any]] = []

    for listing in listings:
        if listing.get("id") == item_id:
            continue
        shared_tags = item_tags & set(listing.get("style_tags", []))
        same_category = listing.get("category") == item_category
        same_size = listing.get("size") == new_item.get("size")
        if same_category or len(shared_tags) >= 2 or (same_size and shared_tags):
            comparables.append(listing)

    if not comparables:
        return {
            "assessment": "unknown",
            "item_price": float(new_item.get("price", 0)),
            "average_comparable_price": None,
            "comparable_count": 0,
            "comparable_titles": [],
            "reasoning": "I did not find enough similar listings in the mock dataset to compare this price.",
        }

    item_price = float(new_item.get("price", 0))
    average_price = sum(float(item.get("price", 0)) for item in comparables) / len(comparables)
    difference = item_price - average_price
    percent_difference = (difference / average_price) * 100 if average_price else 0

    if percent_difference <= -15:
        assessment = "good deal"
    elif percent_difference >= 20:
        assessment = "pricey"
    else:
        assessment = "fair"

    comparable_titles = [
        f"{item.get('title')} (${float(item.get('price', 0)):.0f})"
        for item in sorted(comparables, key=lambda row: float(row.get("price", 0)))[:3]
    ]
    reasoning = (
        f"{new_item.get('title')} is ${item_price:.0f}, compared with an average "
        f"of ${average_price:.0f} across {len(comparables)} similar listing(s): "
        f"{', '.join(comparable_titles)}."
    )

    return {
        "assessment": assessment,
        "item_price": item_price,
        "average_comparable_price": round(average_price, 2),
        "comparable_count": len(comparables),
        "comparable_titles": comparable_titles,
        "reasoning": reasoning,
    }


def get_trend_awareness(new_item: dict[str, Any], size: str | None = None) -> dict[str, Any]:
    """Return trend context for the selected item.

    Args:
        new_item: Listing dictionary selected by the agent.
        size: Optional requested size used to choose size-relevant notes.

    Returns:
        A dictionary with source, trend_tags, styling_tip, and reasoning. If no
        selected item is available, returns an "unknown" trend response with an
        explanatory reason.
    """
    if not new_item:
        return {
            "source": "mock recent resale tag snapshot",
            "trend_tags": [],
            "styling_tip": "",
            "reasoning": "I need a selected listing before checking trend context.",
        }

    trend_snapshot = {
        "tops": {
            "trend_tags": ["rugby stripes", "baby tees", "faded graphics"],
            "styling_tip": "Style the top with relaxed denim or a structured layer so it reads current instead of costume-y.",
        },
        "bottoms": {
            "trend_tags": ["long denim", "pleated minis", "low-slung cargos"],
            "styling_tip": "Balance the bottom with a cleaner top and one strong shoe shape.",
        },
        "outerwear": {
            "trend_tags": ["boxy jackets", "moto layers", "oversized denim"],
            "styling_tip": "Let the jacket be the outer frame and keep the base outfit simple.",
        },
        "knitwear": {
            "trend_tags": ["grandpa cardigans", "soft layering", "chunky texture"],
            "styling_tip": "Use the knit as a texture layer over a slimmer base.",
        },
        "dresses": {
            "trend_tags": ["90s slips", "daytime dresses", "soft minimalism"],
            "styling_tip": "Dress it down with flat shoes or a casual jacket for the current slip-dress look.",
        },
        "shoes": {
            "trend_tags": ["chunky soles", "mary janes", "lug soles"],
            "styling_tip": "Echo the shoe weight with one other grounded piece, like denim or a structured bag.",
        },
        "accessories": {
            "trend_tags": ["small shoulder bags", "soft suede", "90s hardware"],
            "styling_tip": "Keep the outfit simple enough that the accessory shape is visible.",
        },
    }
    category = new_item.get("category")
    trend = trend_snapshot.get(
        category,
        {
            "trend_tags": ["secondhand staples", "personal styling"],
            "styling_tip": "Let the thrifted item lead and keep the rest wearable.",
        },
    )
    size_note = f" Requested size {size} is considered in the styling note." if size else ""
    return {
        "source": "mock recent resale tag snapshot based on public fashion-platform style tags",
        "trend_tags": trend["trend_tags"],
        "styling_tip": trend["styling_tip"],
        "reasoning": (
            f"{new_item.get('title')} matches current tags like "
            f"{', '.join(trend['trend_tags'])}.{size_note}"
        ),
    }


def suggest_outfit(new_item: dict[str, Any], wardrobe: dict[str, Any]) -> str:
    """Suggest a complete outfit using the new listing and user's wardrobe.

    Args:
        new_item: Listing dictionary selected by the agent.
        wardrobe: Dictionary with an "items" list of owned wardrobe pieces.

    Returns:
        A user-facing outfit suggestion string. Empty wardrobes return general
        styling advice instead of raising an exception.
    """
    if not new_item:
        return "I need a selected listing before I can build an outfit."

    items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    wardrobe_lines = [
        f"- {item.get('name')} ({item.get('category')}; colors: {', '.join(item.get('colors', []))}; tags: {', '.join(item.get('style_tags', []))})"
        for item in items
    ]
    prompt = (
        f"New secondhand item: {_format_item(new_item)}\n"
        f"Details: {new_item.get('description', '')}\n"
        f"User wardrobe:\n{chr(10).join(wardrobe_lines) if wardrobe_lines else '- Empty wardrobe'}\n\n"
        "Suggest one complete outfit in 2-4 sentences. If the wardrobe is "
        "empty, give practical styling advice using common closet basics."
    )
    llm_response = _call_groq(prompt, temperature=0.65)
    if llm_response:
        return llm_response

    title = new_item.get("title", "the new piece")
    category = new_item.get("category", "piece")
    item_tags = set(new_item.get("style_tags", []))

    if not items:
        return (
            f"Start with {title} as the statement {category}. Pair it with a "
            "clean closet basics base, like relaxed denim or a "
            "simple black skirt, then add everyday sneakers or boots. Keep the "
            "colors simple so the thrifted piece feels intentional."
        )

    def first_item(categories: set[str], shared_tag_bonus: bool = True) -> dict[str, Any] | None:
        ranked: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            if item.get("category") not in categories:
                continue
            score = 0
            if shared_tag_bonus:
                score += len(item_tags & set(item.get("style_tags", [])))
            if "black" in item.get("colors", []):
                score += 1
            ranked.append((score, item))
        ranked.sort(key=lambda row: -row[0])
        return ranked[0][1] if ranked else None

    bottom = first_item({"bottoms"})
    shoes = first_item({"shoes"})
    layer = first_item({"outerwear", "knitwear"})
    accessory = first_item({"accessories"}, shared_tag_bonus=False)

    pieces = [title]
    if bottom:
        pieces.append(bottom["name"])
    if shoes:
        pieces.append(shoes["name"])
    if layer and new_item.get("category") not in {"outerwear", "knitwear"}:
        pieces.append(layer["name"])
    if accessory:
        pieces.append(accessory["name"])

    styling_note = "Let the thrifted piece lead, then balance it with shapes you already wear often."
    if "grunge" in item_tags or "edgy" in item_tags:
        styling_note = "Roll or half-tuck the top layer so the look feels slouchy on purpose."
    elif "preppy" in item_tags:
        styling_note = "Keep the lines neat and add one relaxed piece so it does not feel too uniform."
    elif "minimal" in item_tags:
        styling_note = "Keep the palette quiet and use texture instead of extra color."

    return f"Try {', '.join(pieces)}. {styling_note}"


def create_fit_card(outfit: str, new_item: dict[str, Any]) -> str:
    """Create a short shareable outfit caption.

    Args:
        outfit: Outfit suggestion generated by suggest_outfit.
        new_item: Listing dictionary selected by the agent.

    Returns:
        A caption-style string. Returns an informative error string when outfit
        is missing.
    """
    if not outfit or not outfit.strip():
        return "I need an outfit suggestion before I can write a fit card."
    if not new_item:
        return "I need the thrifted item details before I can write a fit card."

    prompt = (
        f"Write one short Instagram-style thrift outfit caption.\n"
        f"Thrifted item: {_format_item(new_item)} from {new_item.get('platform', 'a resale platform')}.\n"
        f"Outfit: {outfit}\n"
        "Make it casual, specific, and under 35 words. Do not sound like a product listing."
    )
    llm_response = _call_groq(prompt, temperature=0.95)
    if llm_response:
        return llm_response

    title = str(new_item.get("title", "this thrift find")).lower()
    platform = new_item.get("platform", "the thrift scroll")
    price = float(new_item.get("price", 0))
    color = ", ".join(new_item.get("colors", [])[:2]) or "found"
    templates = [
        "found this {color} {title} on {platform} for ${price:.0f} and built the whole fit around it. very much keeping this in rotation.",
        "${price:.0f} {platform} find, styled with my closet basics so the {title} gets its moment.",
        "today's thrift math: {title} plus pieces I already own equals an outfit I will absolutely repeat.",
        "secondhand {title}, familiar staples, no overthinking. {platform} did its thing for ${price:.0f}.",
    ]
    return random.choice(templates).format(
        color=color,
        title=title,
        platform=platform,
        price=price,
    )

"""Gradio interface for FitFindr."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from agent import run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


STARTER_SEARCHES = [
    ("Vintage tee", "vintage graphic tee", "M", 30, "Baggy jeans + chunky sneakers"),
    ("Preppy polo", "preppy striped rugby polo", "M", 35, "Straight jeans + loafers"),
    ("Cozy layer", "chunky brown knit cardigan", "Any", 40, "Slip skirt + boots"),
    ("90s dress", "90s silk slip dress", "M", 40, "Sneakers + denim jacket"),
    ("No-result test", "designer ballgown", "XXS", 5, "Anything simple"),
]

STYLE_CHOICES = [
    "Baggy jeans + chunky sneakers",
    "Straight jeans + loafers",
    "Slip skirt + boots",
    "Sneakers + denim jacket",
    "Black basics + boots",
    "Anything simple",
]

BASE_SIZE_CHOICES = ["Any", "XS", "S", "M", "L", "XL", "XXS", "8", "OS"]


def _dataset_size_choices() -> list[str]:
    choices = ["Any"]
    try:
        for item in load_listings():
            item_size = str(item.get("size") or "").strip()
            if item_size and item_size not in choices:
                choices.append(item_size)
    except (OSError, ValueError):
        pass
    for item_size in BASE_SIZE_CHOICES:
        if item_size not in choices:
            choices.append(item_size)
    return choices


SIZE_CHOICES = _dataset_size_choices()

HISTORY_HEADERS = [
    "Save",
    "Time",
    "Looking for",
    "Size",
    "Max price",
    "Mostly wear",
    "Closet profile",
    "Selected item",
    "Selected price",
    "Price check",
    "Fit card",
    "Status",
]

COLOR_MAP = {
    "black": "#181818",
    "charcoal": "#45454b",
    "cream": "#efe5d2",
    "light blue": "#98bfe0",
    "blue": "#4777a7",
    "silver": "#b9c0c7",
    "tan": "#bda982",
    "red": "#bd2d35",
    "navy": "#1f2b48",
    "white": "#f7f5ee",
    "sage": "#9aaa86",
    "green": "#47755c",
    "gray": "#8f9297",
    "brown": "#6b4f3d",
    "brass": "#b18b3b",
}


def _safe(value: Any) -> str:
    return escape(str(value or ""))


def _price_text(value: float | int | None) -> str:
    return "Any" if value is None else f"${float(value):.0f}"


def _parse_price_text(value: Any) -> float | None:
    if value in (None, "", "Any"):
        return None
    try:
        return float(str(value).replace("$", "").strip())
    except ValueError:
        return None


def _wardrobe_from_label(closet_mode: str) -> dict[str, Any]:
    if closet_mode == "No closet items":
        return get_empty_wardrobe()
    return get_example_wardrobe()


def _compose_query(item_description: str, size: str, max_price: float, style_preference: str) -> str:
    price_part = f"under ${float(max_price):.0f}" if max_price else ""
    size_part = "" if size == "Any" else f"size {size}"
    style_part = f"I mostly wear {style_preference}." if style_preference else ""
    return " ".join(part for part in [item_description, price_part, size_part, style_part] if part).strip()


def _choices_update(choices: list[str], value: str | None = None):
    import gradio as gr

    return gr.update(choices=choices, value=value)


def _listing_choice_label(item: dict[str, Any]) -> str:
    return f"{item.get('title', 'Untitled')} | {item.get('size', 'Any')} | {_price_text(item.get('price'))}"


def _listing_choices() -> list[str]:
    try:
        return [_listing_choice_label(item) for item in load_listings()]
    except (OSError, ValueError):
        return []


def load_listing_choice(selected_listing: str | None) -> tuple[str, str, float]:
    """Fill search controls from one of the 40 starter listings."""
    for item in load_listings():
        if _listing_choice_label(item) == selected_listing:
            return (
                str(item.get("title", "")),
                str(item.get("size") or "Any"),
                float(item.get("price", 35)),
            )
    return "", "Any", 35


def _profile_label(profile: dict[str, Any]) -> str:
    return (
        f"{profile.get('size', 'Any')} | "
        f"{_price_text(profile.get('max_price'))} | "
        f"{profile.get('style_preference', 'Anything simple')} | "
        f"{profile.get('closet_mode', 'Sample closet')}"
    )


def _profile_choices(profile_memory: list[dict[str, Any]] | None) -> list[str]:
    return [_profile_label(profile) for profile in profile_memory or []]


def _format_memory_status(profile_memory: list[dict[str, Any]] | None, source: str = "saved") -> str:
    profiles = list(profile_memory or [])
    if not profiles:
        return (
            "<div class='memory-card'>"
            "<strong>Saved profile memory</strong>"
            "<span class='info-dot' data-tip='Profiles save size, max price, mostly-wear style, and closet profile. They do not save the item you are searching for.'>i</span>"
            "<div>None yet. Add a fit to history, then check Save on that row.</div>"
            "</div>"
        )
    label = "reused" if source == "remembered" else "saved"
    saved_list = "".join(f"<li>{_safe(_profile_label(profile))}</li>" for profile in profiles[:3])
    tooltip = " | ".join(_safe(_profile_label(profile)) for profile in profiles[:3])
    return (
        "<div class='memory-card'>"
        f"<strong>Saved profile memory {label}</strong>"
        f"<span class='info-dot' data-tip='Stored profiles: {tooltip}'>i</span>"
        f"<ol>{saved_list}</ol>"
        "</div>"
    )


def _profile_from_preview(preview_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "size": preview_state.get("size", "Any"),
        "max_price": preview_state.get("max_price"),
        "style_preference": preview_state.get("style_preference", "Anything simple"),
        "closet_mode": preview_state.get("closet_mode", "Sample closet"),
    }


def _dedupe_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_profiles = []
    seen_labels = set()
    for profile in profiles:
        label = _profile_label(profile)
        if label not in seen_labels:
            unique_profiles.append(profile)
            seen_labels.add(label)
    return unique_profiles[:3]


def _save_profile(
    preview_state: dict[str, Any],
    profile_memory: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    profile = _profile_from_preview(preview_state)
    return _dedupe_profiles([profile, *list(profile_memory or [])])


def _profile_from_history_row(row: list[Any]) -> dict[str, Any]:
    style_text = str(row[5] or "Anything simple")
    style_preference = style_text.split(" (", 1)[0]
    return {
        "size": str(row[3] or "Any"),
        "max_price": _parse_price_text(row[4]),
        "style_preference": style_preference,
        "closet_mode": str(row[6] or "Sample closet"),
    }


def _row_is_checked(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "checked"}
    return bool(value)


def _rows_from_table(history: Any) -> list[list[Any]]:
    if history is None:
        return []
    if hasattr(history, "fillna") and hasattr(history, "to_numpy"):
        return history.fillna("").to_numpy().tolist()
    return list(history or [])


def apply_saved_profile(
    selected_profile: str | None,
    profile_memory: list[dict[str, Any]] | None,
) -> tuple[Any, Any, Any, Any, str]:
    profiles = list(profile_memory or [])
    for profile in profiles:
        if _profile_label(profile) == selected_profile:
            ordered_profiles = [profile, *[item for item in profiles if _profile_label(item) != selected_profile]][:3]
            return (
                profile.get("size", "Any"),
                profile.get("max_price", 35),
                profile.get("style_preference", "Anything simple"),
                profile.get("closet_mode", "Sample closet"),
                _format_memory_status(ordered_profiles, "remembered"),
            )
    return (
        "Any",
        35,
        "Anything simple",
        "Sample closet",
        _format_memory_status(profiles, "saved"),
    )


def remove_saved_profile(
    selected_profile: str | None,
    profile_memory: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], str, Any]:
    """Remove the selected saved profile from session memory."""
    profiles = [
        profile
        for profile in list(profile_memory or [])
        if _profile_label(profile) != selected_profile
    ]
    choices = _profile_choices(profiles)
    return (
        profiles,
        _format_memory_status(profiles, "saved"),
        _choices_update(choices, choices[0] if choices else None),
    )


def _format_price_assessment(price_assessment: dict[str, Any] | None) -> str:
    if not price_assessment:
        return "No price comparison yet."
    assessment = _safe(str(price_assessment.get("assessment", "unknown")).title())
    reasoning = _safe(price_assessment.get("reasoning", ""))
    return f"<span class='status-pill'>{assessment}</span><span>{reasoning}</span>"


def _format_comparable_cards(price_assessment: dict[str, Any] | None) -> str:
    if not price_assessment or price_assessment.get("comparable_count", 0) == 0:
        return (
            "<div class='compare-strip'>"
            "<div class='compare-heading'>Comparable listings</div>"
            "<p>No comparable listings were available for this item.</p>"
            "</div>"
        )

    item_price = _price_text(price_assessment.get("item_price"))
    average_price = _price_text(price_assessment.get("average_comparable_price"))
    cards = [
        (
            "<div class='compare-card selected-compare'>"
            "<span>Selected</span>"
            f"<strong>{item_price}</strong>"
            "</div>"
        ),
        (
            "<div class='compare-card average-compare'>"
            "<span>Comparable avg</span>"
            f"<strong>{average_price}</strong>"
            "</div>"
        ),
    ]
    for title in price_assessment.get("comparable_titles", []):
        cards.append(
            "<div class='compare-card'>"
            "<span>Similar</span>"
            f"<strong>{_safe(title)}</strong>"
            "</div>"
        )
    dots = "".join(
        f"<span class='compare-dot{' active' if index == 0 else ''}'></span>"
        for index in range(len(cards))
    )
    return (
        "<div class='compare-strip'>"
        "<div class='compare-heading'>Price comparison</div>"
        f"<div class='compare-cards'>{''.join(cards)}</div>"
        f"<div class='compare-dots'>{dots}</div>"
        "<small class='compare-help'>Pick one of these similar price items in the selector below, then click Preview selected price item.</small>"
        "</div>"
    )


def _comparable_choices(session: dict[str, Any]) -> list[str]:
    item = session.get("selected_item") or {}
    choices = []
    if item:
        choices.append(f"Selected: {item.get('title')} (${float(item.get('price', 0)):.0f})")
    price_assessment = session.get("price_assessment") or {}
    choices.extend(price_assessment.get("comparable_titles", []))
    return choices


def _title_from_choice(choice: str | None) -> str:
    if not choice:
        return ""
    title = choice.replace("Selected: ", "", 1)
    return title.split(" ($", 1)[0].strip()


def _session_to_preview_state(
    session: dict[str, Any],
    item_description: str,
    size: str,
    max_price: float,
    style_preference: str,
    style_source: str,
    closet_mode: str,
) -> dict[str, Any]:
    return {
        "session": session,
        "item_description": item_description,
        "size": size,
        "max_price": max_price,
        "style_preference": style_preference,
        "style_source": style_source,
        "closet_mode": closet_mode,
    }


def _find_listing_by_title(title: str) -> dict[str, Any] | None:
    for listing in load_listings():
        if listing.get("title") == title:
            return listing
    return None


def _color_swatches(colors: list[str]) -> str:
    if not colors:
        return "<span class='swatch empty'></span>"
    swatches = []
    for color in colors[:4]:
        hex_value = COLOR_MAP.get(str(color).lower(), "#d6d0c5")
        swatches.append(
            f"<span class='swatch' title='{_safe(color)}' style='background:{hex_value}'></span>"
        )
    return "".join(swatches)


def _garment_svg(item: dict[str, Any]) -> str:
    colors = item.get("colors", [])
    primary = COLOR_MAP.get(str(colors[0]).lower(), "#47755c") if colors else "#47755c"
    secondary = COLOR_MAP.get(str(colors[1]).lower(), "#f7f5ee") if len(colors) > 1 else "#f7f5ee"
    category = item.get("category")

    if category in {"tops", "knitwear"}:
        shape = (
            f"<path d='M70 58 L105 38 L136 68 L122 94 L108 83 L108 174 L52 174 L52 83 L38 94 L24 68 L55 38 Z' "
            f"fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M58 40 Q80 58 102 40 L96 69 Q80 82 64 69 Z' fill='{secondary}' opacity='.92'/>"
            f"<path d='M56 112 H106' stroke='{secondary}' stroke-width='7' opacity='.65'/>"
            f"<path d='M56 132 H106' stroke='{secondary}' stroke-width='7' opacity='.65'/>"
        )
    elif category == "dresses":
        shape = (
            f"<path d='M62 38 H98 L110 83 L132 176 H28 L50 83 Z' fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M62 38 L50 82 H110 L98 38 Z' fill='{secondary}' opacity='.55'/>"
            f"<path d='M62 38 L52 18 M98 38 L108 18' stroke='#222' stroke-width='5' stroke-linecap='round'/>"
        )
    elif category == "bottoms":
        shape = (
            f"<path d='M52 38 H108 L116 176 H89 L80 82 L71 176 H44 Z' fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M52 66 H108 M80 38 V82' stroke='{secondary}' stroke-width='5' opacity='.55'/>"
        )
    elif category == "outerwear":
        shape = (
            f"<path d='M49 42 L78 34 L111 42 L128 174 H86 L80 76 L74 174 H32 Z' fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M78 34 L80 76 L111 42 M78 34 L74 76 L49 42' fill='none' stroke='{secondary}' stroke-width='5' opacity='.7'/>"
            f"<path d='M80 76 V174' stroke='#222' stroke-width='3'/>"
        )
    elif category == "shoes":
        shape = (
            f"<path d='M24 116 Q63 80 92 112 Q113 132 142 134 L142 156 H28 Q18 148 24 116 Z' fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M40 131 H138' stroke='{secondary}' stroke-width='8' opacity='.8'/>"
        )
    elif category == "accessories":
        shape = (
            f"<path d='M45 78 H116 L128 170 H32 Z' fill='{primary}' stroke='#222' stroke-width='3'/>"
            f"<path d='M55 78 Q80 24 106 78' fill='none' stroke='#222' stroke-width='7'/>"
            f"<circle cx='80' cy='121' r='10' fill='{secondary}' opacity='.8'/>"
        )
    else:
        shape = f"<circle cx='80' cy='105' r='55' fill='{primary}' stroke='#222' stroke-width='3'/>"

    return (
        "<svg class='garment-svg' viewBox='0 0 160 200' role='img' aria-label='Garment preview'>"
        f"{shape}"
        "</svg>"
    )


def _visual_tile(item: dict[str, Any]) -> str:
    colors = item.get("colors", [])
    primary = COLOR_MAP.get(str(colors[0]).lower(), "#f4f0e8") if colors else "#f4f0e8"
    secondary = COLOR_MAP.get(str(colors[1]).lower(), "#d7e0de") if len(colors) > 1 else "#d7e0de"
    platform = _safe(item.get("platform", "Mock resale source"))
    return (
        f"<div class='listing-art' style='--primary:{primary}; --secondary:{secondary};'>"
        f"<div class='art-tag'>Mock marketplace: {platform}</div>"
        f"{_garment_svg(item)}"
        f"<div class='art-swatches'>{_color_swatches(colors)}</div>"
        "</div>"
    )


def _format_listing_panel(session: dict[str, Any]) -> str:
    if session.get("error") and not session.get("selected_item"):
        return _format_error_card(session["error"], session)

    item = session.get("selected_item")
    if not item:
        return "<div class='empty-card'>Run a search to see a selected listing.</div>"

    tags = "".join(f"<span class='tag'>{_safe(tag)}</span>" for tag in item.get("style_tags", []))
    colors = ", ".join(_safe(color) for color in item.get("colors", []))
    title = _safe(item.get("title", "Selected listing"))
    description = _safe(item.get("description", ""))
    platform = _safe(item.get("platform", "Mock resale source"))
    condition = _safe(item.get("condition", "Unknown"))
    size = _safe(item.get("size", "Unknown"))
    price = float(item.get("price", 0))

    return (
        "<section class='result-card listing-card'>"
        f"{_visual_tile(item)}"
        "<div class='listing-copy'>"
        "<div class='eyebrow'>Selected mock listing</div>"
        f"<h2>{title}</h2>"
        f"<div class='listing-meta'><strong>${price:.0f}</strong><span>Marketplace: {platform}</span><span>Size {size}</span><span>{condition}</span></div>"
        f"<p>{description}</p>"
        f"<div class='tag-row'>{tags}</div>"
        f"<div class='detail-line'><span>Colors</span><strong>{colors}</strong></div>"
        f"<div class='price-check'>{_format_price_assessment(session.get('price_assessment'))}</div>"
        f"{_format_comparable_cards(session.get('price_assessment'))}"
        "</div>"
        "</section>"
    )


def _format_outfit_panel(session: dict[str, Any]) -> str:
    if session.get("error") and not session.get("outfit_suggestion"):
        return _format_error_card(session["error"], session)
    outfit = _safe(session.get("outfit_suggestion") or "No outfit suggestion yet.")
    item = session.get("selected_item") or {}
    item_title = _safe(item.get("title", "the thrifted item"))
    trend = session.get("trend_context") or {}
    trend_tags = ", ".join(_safe(tag) for tag in trend.get("trend_tags", []))
    trend_block = ""
    if trend:
        trend_block = (
            "<div class='trend-note'>"
            "<strong>Trend cue</strong>"
            f"<span>{_safe(trend.get('reasoning', ''))}</span>"
            f"<small>Tags: {trend_tags}</small>"
            "</div>"
        )
    return (
        "<section class='result-card outfit-card'>"
        "<div class='eyebrow'>Outfit recipe</div>"
        f"<h2>Style {item_title}</h2>"
        f"<p>{outfit}</p>"
        f"{trend_block}"
        "<div class='mini-steps'>"
        "<span>Anchor piece</span>"
        "<span>Closet match</span>"
        "<span>Styling move</span>"
        "</div>"
        "</section>"
    )


def _format_fit_card_panel(session: dict[str, Any]) -> str:
    if session.get("error") and not session.get("fit_card"):
        return _format_error_card(session["error"], session)

    caption = _safe(session.get("fit_card") or "No fit card yet.")
    item = session.get("selected_item") or {}
    title = _safe(item.get("title", "FitFindr"))
    price = float(item.get("price", 0)) if item else 0
    platform = _safe(item.get("platform", "mock resale"))
    return (
        "<section class='token-wrap'>"
        "<div class='fit-token'>"
        "<div class='token-topline'><span>FIT CARD</span><span>SHARE TOKEN</span></div>"
        f"<h2>{caption}</h2>"
        "<div class='token-footer'>"
        f"<span>{title}</span>"
        f"<span>${price:.0f} from {platform}</span>"
        "</div>"
        "</div>"
        "</section>"
    )


def _format_trace_panel(session: dict[str, Any]) -> str:
    trace = session.get("trace", [])
    if not trace:
        return "<div class='empty-card'>Run a search to see the agent steps.</div>"
    rows = "".join(f"<li>{_safe(step)}</li>" for step in trace)
    return (
        "<section class='trace-card'>"
        "<div class='eyebrow'>Agent steps</div>"
        f"<ol>{rows}</ol>"
        "</section>"
    )


def _format_error_card(message: str, session: dict[str, Any]) -> str:
    trace = " ".join(_safe(step) for step in session.get("trace", []))
    return (
        "<section class='result-card error-card'>"
        "<div class='eyebrow'>No match found</div>"
        f"<h2>{_safe(message)}</h2>"
        "<p>Try a broader item name, choose Any size, or raise the max price.</p>"
        f"<small>{trace}</small>"
        "</section>"
    )


def _history_row(
    session: dict[str, Any],
    item_description: str,
    size: str,
    max_price: float,
    style_preference: str,
    style_source: str,
    closet_mode: str,
) -> list[str]:
    selected = session.get("selected_item") or {}
    price_assessment = session.get("price_assessment") or {}
    status = "No match" if session.get("error") else "Complete"
    return [
        False,
        datetime.now().strftime("%H:%M:%S"),
        item_description,
        size,
        _price_text(max_price),
        f"{style_preference} ({style_source})",
        closet_mode,
        selected.get("title", "None"),
        _price_text(selected.get("price")) if selected else "None",
        price_assessment.get("assessment", "None"),
        session.get("fit_card") or session.get("error") or "",
        status,
    ]


def handle_query(
    item_description: str,
    size: str,
    max_price: float,
    style_preference: str,
    closet_mode: str,
) -> tuple[str, str, str, str, dict[str, Any], Any]:
    """Preview an agent result without writing to the history table."""
    effective_style, style_source = style_preference, "new"
    normalized_size = None if size == "Any" else size
    query = _compose_query(item_description, size, max_price, effective_style)
    wardrobe = _wardrobe_from_label(closet_mode)
    session = run_agent(query, wardrobe=wardrobe, size=normalized_size, max_price=max_price)
    preview_state = _session_to_preview_state(
        session,
        item_description,
        size,
        max_price,
        effective_style,
        style_source,
        closet_mode,
    )
    comparable_choices = _comparable_choices(session)

    return (
        _format_listing_panel(session),
        _format_outfit_panel(session),
        _format_fit_card_panel(session),
        _format_trace_panel(session),
        preview_state,
        _choices_update(comparable_choices, comparable_choices[0] if comparable_choices else None),
    )


def preview_comparable_item(
    comparable_choice: str | None,
    preview_state: dict[str, Any] | None,
) -> tuple[str, str, str, str, dict[str, Any], Any]:
    """Preview a comparable price item selected from the comparison list."""
    if not preview_state:
        empty = "<div class='empty-card'>Run a search before selecting a comparison item.</div>"
        return empty, empty, empty, empty, {}, _choices_update([], None)

    title = _title_from_choice(comparable_choice)
    listing = _find_listing_by_title(title)
    if not listing:
        session = preview_state["session"]
        choices = _comparable_choices(session)
        return (
            _format_listing_panel(session),
            _format_outfit_panel(session),
            _format_fit_card_panel(session),
            _format_trace_panel(session),
            preview_state,
            _choices_update(choices, comparable_choice),
        )

    item_description = listing["title"]
    size = str(listing.get("size") or "Any")
    max_price = max(float(listing.get("price", 0)), float(preview_state.get("max_price") or 0))
    style_preference = preview_state.get("style_preference", "Anything simple")
    closet_mode = preview_state.get("closet_mode", "Sample closet")
    normalized_size = None if size == "Any" else size
    query = _compose_query(item_description, size, max_price, style_preference)
    session = run_agent(
        query,
        wardrobe=_wardrobe_from_label(closet_mode),
        size=normalized_size,
        max_price=max_price,
    )
    updated_preview_state = _session_to_preview_state(
        session,
        item_description,
        size,
        max_price,
        style_preference,
        "comparison",
        closet_mode,
    )
    choices = _comparable_choices(session)
    selected_choice = choices[0] if choices else None
    return (
        _format_listing_panel(session),
        _format_outfit_panel(session),
        _format_fit_card_panel(session),
        _format_trace_panel(session),
        updated_preview_state,
        _choices_update(choices, selected_choice),
    )


def add_preview_to_history(
    preview_state: dict[str, Any] | None,
    history: list[list[str]] | None,
) -> tuple[list[list[str]], list[list[str]]]:
    """Write the currently previewed fit into the spreadsheet-style history."""
    if not preview_state:
        rows = list(history or [])
        return rows, rows

    rows = list(history or [])
    rows.insert(
        0,
        _history_row(
            preview_state["session"],
            preview_state["item_description"],
            preview_state["size"],
            preview_state["max_price"],
            preview_state["style_preference"],
            preview_state["style_source"],
            preview_state["closet_mode"],
        ),
    )
    rows = rows[:12]
    return rows, rows


def save_profiles_from_history(
    history: list[list[Any]] | None,
    profile_memory: list[dict[str, Any]] | None,
) -> tuple[list[list[Any]], list[dict[str, Any]], str, Any]:
    """Save profile memory from checked rows in the history table."""
    rows = _rows_from_table(history)
    checked_profiles = [_profile_from_history_row(row) for row in rows if row and _row_is_checked(row[0])]
    profiles = _dedupe_profiles([*checked_profiles, *list(profile_memory or [])])
    choices = _profile_choices(profiles)
    return (
        rows,
        profiles,
        _format_memory_status(profiles, "saved"),
        _choices_update(choices, choices[0] if choices else None),
    )


def load_starter(label: str) -> tuple[str, str, int, str]:
    for starter_label, item, size, price, style in STARTER_SEARCHES:
        if starter_label == label:
            return item, size, price, style
    return STARTER_SEARCHES[0][1], STARTER_SEARCHES[0][2], STARTER_SEARCHES[0][3], STARTER_SEARCHES[0][4]


CUSTOM_CSS = """
:root {
  --ink: #20201f;
  --muted: #69645d;
  --line: #ddd7cc;
  --paper: #fbfaf7;
  --panel: #ffffff;
  --accent: #2f6f64;
  --accent-2: #9f4f3f;
  --accent-3: #d9b75f;
}

.gradio-container {
  background: linear-gradient(180deg, #f7f4ee 0%, #fdfcf9 58%, #f5f7f4 100%);
  color: var(--ink);
}

.app-shell {
  max-width: 1220px;
  margin: 0 auto;
}

.hero-band {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 22px;
  background: #fffdf8;
  box-shadow: 0 14px 34px rgba(42, 36, 28, 0.08);
}

.hero-band h1 {
  margin: 0 0 8px;
  font-size: 38px;
  line-height: 1.05;
  letter-spacing: 0;
}

.hero-band p {
  margin: 0;
  color: var(--muted);
  font-size: 15px;
}

.prompt-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  padding: 16px;
}

.helper-note {
  margin: 4px 0 10px;
  color: var(--muted);
  font-size: 13px;
}

.starter-label {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.suggestion-chip {
  min-width: 132px !important;
  border-radius: 999px !important;
  border: 1px solid var(--line) !important;
  background: #fffaf1 !important;
  color: var(--ink) !important;
  box-shadow: none !important;
}

.suggestion-chip:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

#find-fit-button {
  border-radius: 999px !important;
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: white !important;
}

.result-card, .trace-card, .empty-card {
  min-height: 230px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: 0 10px 28px rgba(42, 36, 28, 0.07);
  overflow: hidden;
}

.listing-card {
  display: grid;
  grid-template-columns: minmax(170px, 230px) minmax(0, 1fr);
  max-width: 100%;
}

.listing-art {
  position: relative;
  min-height: 310px;
  padding: 16px;
  background:
    radial-gradient(circle at 28% 18%, rgba(255,255,255,.55), transparent 30%),
    linear-gradient(135deg, color-mix(in srgb, var(--primary) 72%, white), var(--secondary));
  display: flex;
  align-items: center;
  justify-content: center;
}

.art-tag {
  position: absolute;
  top: 14px;
  left: 14px;
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 800;
  color: var(--ink);
}

.garment-svg {
  width: min(78%, 210px);
  height: auto;
  filter: drop-shadow(0 16px 20px rgba(0, 0, 0, 0.22));
}

.art-swatches {
  position: absolute;
  bottom: 16px;
  left: 16px;
  display: flex;
  gap: 7px;
}

.swatch {
  width: 19px;
  height: 19px;
  border-radius: 999px;
  border: 1px solid rgba(32, 32, 31, 0.28);
  display: inline-block;
}

.listing-copy, .outfit-card, .trace-card {
  padding: 20px;
  min-width: 0;
}

.eyebrow {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.result-card h2, .fit-token h2 {
  margin: 0 0 12px;
  font-size: 24px;
  line-height: 1.15;
  letter-spacing: 0;
}

.result-card p {
  margin: 0 0 14px;
  color: var(--muted);
  line-height: 1.5;
}

.listing-meta, .tag-row, .mini-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.listing-meta span, .listing-meta strong, .tag, .mini-steps span, .status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: #f8f5ef;
  font-size: 12px;
}

.listing-meta strong, .status-pill {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.detail-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 13px;
}

.price-check {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  background: #f1f7f4;
  color: #2f514b;
  font-size: 13px;
  line-height: 1.4;
}

.compare-strip {
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  background: #fffaf1;
  border: 1px solid var(--line);
}

.compare-heading {
  margin-bottom: 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.compare-cards {
  display: flex;
  gap: 8px;
  max-width: 100%;
  overflow-x: auto;
  padding-bottom: 4px;
  scroll-snap-type: x proximity;
  -webkit-overflow-scrolling: touch;
}

.compare-card {
  flex: 0 0 138px;
  min-height: 72px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: white;
  scroll-snap-align: start;
}

.compare-card span {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.compare-card strong {
  color: var(--ink);
  font-size: 13px;
  line-height: 1.25;
}

.selected-compare {
  background: #eef6f2;
  border-color: #bdd8d0;
}

.average-compare {
  background: #f7f2e6;
}

.compare-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
}

.compare-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  border: 1px solid var(--accent);
  background: transparent;
}

.compare-dot.active {
  background: var(--accent);
}

.token-wrap {
  min-height: 230px;
  display: flex;
  align-items: stretch;
}

.fit-token {
  width: 100%;
  min-height: 230px;
  border-radius: 8px;
  padding: 24px;
  background:
    linear-gradient(90deg, var(--accent) 0 10px, transparent 10px),
    linear-gradient(145deg, #fffaf0 0%, #f7efe0 56%, #e7f0ec 100%);
  color: var(--ink);
  border: 1px solid #d6cab8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 16px 38px rgba(32, 32, 31, 0.14);
}

.token-topline, .token-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.fit-token h2 {
  margin: 28px 0;
  font-size: 28px;
}

.trace-card ol {
  margin: 0;
  padding-left: 20px;
}

.trace-card li {
  margin-bottom: 8px;
  color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.error-card {
  padding: 20px;
  border-color: #e0b6ac;
  background: #fff7f4;
}

.error-card h2 {
  color: #8f3828;
  font-size: 20px;
}

.error-card small {
  display: block;
  color: #8a6d65;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  line-height: 1.45;
}

.history-note {
  margin-top: 8px;
  color: var(--muted);
  font-size: 13px;
}

.memory-card, .trend-note {
  margin-top: 10px;
  padding: 11px 12px;
  border-radius: 8px;
  background: #f6f2e9;
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 13px;
}

.memory-card ol {
  margin: 8px 0 0 18px;
  padding: 0;
}

.memory-card li {
  margin: 2px 0;
}

.info-dot {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 8px;
  border-radius: 999px;
  background: var(--accent);
  color: white;
  font-size: 12px;
  font-weight: 900;
  cursor: help;
}

.info-dot:hover::after {
  content: attr(data-tip);
  position: absolute;
  z-index: 20;
  left: 50%;
  bottom: calc(100% + 8px);
  width: 260px;
  transform: translateX(-50%);
  padding: 10px;
  border-radius: 8px;
  background: #20201f;
  color: white;
  font-size: 12px;
  line-height: 1.35;
  box-shadow: 0 12px 26px rgba(0, 0, 0, .2);
}

.memory-actions button {
  border-radius: 999px !important;
}

.memory-card strong {
  color: var(--accent);
}

.trend-note {
  display: grid;
  gap: 4px;
  background: #eef6f2;
  color: #2f514b;
}

.trend-note strong {
  color: var(--accent);
}

.trend-note small {
  color: #53746e;
}

@media (max-width: 780px) {
  .hero-band h1 {
    font-size: 30px;
  }

  .listing-card {
    grid-template-columns: 1fr;
  }

  .listing-art {
    min-height: 230px;
  }

  .fit-token h2 {
    font-size: 22px;
  }
}
"""


def build_app():
    import gradio as gr

    with gr.Blocks(title="FitFindr") as demo:
        history_state = gr.State([])
        profile_memory_state = gr.State([])
        preview_state = gr.State({})
        with gr.Column(elem_classes=["app-shell"]):
            gr.HTML(
                """
                <section class="hero-band">
                  <h1>FitFindr</h1>
                  <p>Use filters to search mock secondhand listings, style the selected piece with a closet profile, and save each result in the history table.</p>
                </section>
                """
            )
            with gr.Group(elem_classes=["prompt-panel"]):
                gr.HTML(
                    "<p class='helper-note'>Mock marketplaces such as Depop, Poshmark, Gem, and ThredUp are the resale sources in the sample dataset.</p>"
                )
                with gr.Row():
                    item_description = gr.Textbox(
                        label="What item are you looking for?",
                        value="preppy striped rugby polo",
                        placeholder="Examples: vintage graphic tee, slip dress, denim jacket",
                        lines=2,
                    )
                    style_preference = gr.Dropdown(
                        STYLE_CHOICES,
                        value="Straight jeans + loafers",
                        label="I mostly wear",
                    )
                listing_picker = gr.Dropdown(
                    _listing_choices(),
                    label="Browse all 40 starter listings",
                    interactive=True,
                )
                memory_status = gr.HTML(
                    _format_memory_status([])
                )
                with gr.Row(elem_classes=["memory-actions"]):
                    profile_picker = gr.Dropdown(
                        [],
                        label="Saved profile memory",
                        interactive=True,
                    )
                    apply_profile_button = gr.Button("Apply saved profile", size="sm")
                    remove_profile_button = gr.Button("Remove saved profile", size="sm")
                with gr.Row():
                    size = gr.Dropdown(SIZE_CHOICES, value="M", label="Size")
                    max_price = gr.Slider(5, 80, value=35, step=1, label="Max price")
                    closet_mode = gr.Radio(
                        ["Sample closet", "No closet items"],
                        value="Sample closet",
                        label="Closet profile",
                    )

                gr.HTML("<div class='starter-label'>Starter searches</div>")
                with gr.Row():
                    starter_buttons = [
                        gr.Button(label, elem_classes=["suggestion-chip"], size="sm")
                        for label, *_ in STARTER_SEARCHES
                    ]
                submit = gr.Button(
                    "Find a fit",
                    variant="primary",
                    size="lg",
                    elem_id="find-fit-button",
                )

            with gr.Row():
                listings = gr.HTML(label="Selected listing")
                outfit = gr.HTML(label="Outfit suggestion")
            with gr.Group(elem_classes=["prompt-panel"]):
                gr.HTML(
                    "<div class='starter-label'>Selectable price comparison</div>"
                    "<p class='helper-note'>Choose a comparable price item here, preview it, then add the current fit to history only when you are happy with it.</p>"
                )
                with gr.Row():
                    comparable_picker = gr.Dropdown(
                        [],
                        label="Price item to preview",
                        interactive=True,
                    )
                    preview_comparable_button = gr.Button("Preview selected price item", size="sm")
            with gr.Row():
                fit_card = gr.HTML(label="Fit card")
                trace = gr.HTML(label="Agent steps")

            gr.HTML("<div class='starter-label'>Conversation history</div><p class='history-note'>Each run is saved below like a simple spreadsheet. Check Save on any row to store that row's size, price, style, and closet as profile memory.</p>")
            history_table = gr.Dataframe(
                headers=HISTORY_HEADERS,
                datatype=["bool", *["str"] * (len(HISTORY_HEADERS) - 1)],
                row_count=(0, "dynamic"),
                column_count=(len(HISTORY_HEADERS), "fixed"),
                interactive=True,
                wrap=True,
                label="Search history",
            )
            with gr.Row():
                add_history_button = gr.Button("Add current fit to history", variant="secondary")

            submit.click(
                handle_query,
                inputs=[item_description, size, max_price, style_preference, closet_mode],
                outputs=[
                    listings,
                    outfit,
                    fit_card,
                    trace,
                    preview_state,
                    comparable_picker,
                ],
            )
            listing_picker.change(
                load_listing_choice,
                inputs=listing_picker,
                outputs=[item_description, size, max_price],
            )
            preview_comparable_button.click(
                preview_comparable_item,
                inputs=[comparable_picker, preview_state],
                outputs=[listings, outfit, fit_card, trace, preview_state, comparable_picker],
            )
            add_history_button.click(
                add_preview_to_history,
                inputs=[preview_state, history_state],
                outputs=[history_table, history_state],
            )
            history_table.input(
                save_profiles_from_history,
                inputs=[history_table, profile_memory_state],
                outputs=[history_state, profile_memory_state, memory_status, profile_picker],
            )
            profile_picker.change(
                apply_saved_profile,
                inputs=[profile_picker, profile_memory_state],
                outputs=[size, max_price, style_preference, closet_mode, memory_status],
            )
            apply_profile_button.click(
                apply_saved_profile,
                inputs=[profile_picker, profile_memory_state],
                outputs=[size, max_price, style_preference, closet_mode, memory_status],
            )
            remove_profile_button.click(
                remove_saved_profile,
                inputs=[profile_picker, profile_memory_state],
                outputs=[profile_memory_state, memory_status, profile_picker],
            )
            for starter_button, (label, starter_item, starter_size, starter_price, starter_style) in zip(
                starter_buttons,
                STARTER_SEARCHES,
            ):
                starter_button.click(
                    lambda item=starter_item, selected_size=starter_size, price=starter_price, style=starter_style: (
                        item,
                        selected_size,
                        price,
                        style,
                    ),
                    inputs=None,
                    outputs=[item_description, size, max_price, style_preference],
                )
    return demo


if __name__ == "__main__":
    build_app().launch(css=CUSTOM_CSS)

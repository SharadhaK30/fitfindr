from __future__ import annotations

import pandas as pd

from app import (
    add_preview_to_history,
    apply_saved_profile,
    handle_query,
    preview_comparable_item,
    remove_saved_profile,
    save_profiles_from_history,
)


def test_profile_memory_saves_from_history_checkbox_and_reuses_filters():
    preview = handle_query(
        "vintage graphic tee",
        "M",
        30,
        "Baggy jeans + chunky sneakers",
        "Sample closet",
    )
    rows, _ = add_preview_to_history(preview[4], [])
    rows[0][0] = True
    _, profiles, status, profile_update = save_profiles_from_history(rows, [])
    applied_size, applied_price, applied_style, applied_closet, applied_status = apply_saved_profile(
        profile_update["value"],
        profiles,
    )

    assert len(profiles) == 1
    assert profiles[0] == {
        "size": "M",
        "max_price": 30,
        "style_preference": "Baggy jeans + chunky sneakers",
        "closet_mode": "Sample closet",
    }
    assert profile_update["choices"] == ["M | $30 | Baggy jeans + chunky sneakers | Sample closet"]
    assert applied_size == "M"
    assert applied_price == 30
    assert applied_style == "Baggy jeans + chunky sneakers"
    assert applied_closet == "Sample closet"
    assert "Saved profile memory saved" in status
    assert "Saved profile memory reused" in applied_status
    assert any("Baggy jeans + chunky sneakers" in str(cell) for cell in rows[0])


def test_profile_memory_keeps_three_recent_unique_profiles():
    previews = [
        handle_query("preppy striped rugby polo", "M", 35, "Straight jeans + loafers", "Sample closet"),
        handle_query("cream cable knit cardigan", "L", 30, "Slip skirt + boots", "No closet items"),
        handle_query("90s slip dress", "M", 40, "Sneakers + denim jacket", "Sample closet"),
        handle_query("vintage graphic tee", "S", 25, "Black basics + boots", "Sample closet"),
    ]
    profiles = []
    history = []
    for preview in previews:
        history, _ = add_preview_to_history(preview[4], history)
        history[0][0] = True
        _, profiles, _, profile_update = save_profiles_from_history(history, profiles)

    assert len(profiles) == 3
    assert profile_update["choices"] == [
        "S | $25 | Black basics + boots | Sample closet",
        "M | $40 | Sneakers + denim jacket | Sample closet",
        "L | $30 | Slip skirt + boots | No closet items",
    ]


def test_profile_memory_accepts_gradio_dataframe_edits():
    preview = handle_query(
        "preppy striped rugby polo",
        "M",
        35,
        "Straight jeans + loafers",
        "Sample closet",
    )
    rows, _ = add_preview_to_history(preview[4], [])
    rows[0][0] = True
    dataframe = pd.DataFrame(rows)

    _, profiles, status, profile_update = save_profiles_from_history(dataframe, [])

    assert profiles[0]["size"] == "M"
    assert profiles[0]["max_price"] == 35
    assert profiles[0]["style_preference"] == "Straight jeans + loafers"
    assert profiles[0]["closet_mode"] == "Sample closet"
    assert "Saved profile memory saved" in status
    assert profile_update["value"] == "M | $35 | Straight jeans + loafers | Sample closet"


def test_remove_saved_profile_updates_memory_and_dropdown():
    profiles = [
        {
            "size": "M",
            "max_price": 35,
            "style_preference": "Straight jeans + loafers",
            "closet_mode": "Sample closet",
        },
        {
            "size": "S",
            "max_price": 25,
            "style_preference": "Black basics + boots",
            "closet_mode": "Sample closet",
        },
    ]

    updated_profiles, status, profile_update = remove_saved_profile(
        "M | $35 | Straight jeans + loafers | Sample closet",
        profiles,
    )

    assert updated_profiles == [profiles[1]]
    assert "Straight jeans + loafers" not in status
    assert profile_update["choices"] == ["S | $25 | Black basics + boots | Sample closet"]
    assert profile_update["value"] == "S | $25 | Black basics + boots | Sample closet"


def test_remove_saved_profile_clears_last_profile():
    profiles = [
        {
            "size": "M",
            "max_price": 35,
            "style_preference": "Straight jeans + loafers",
            "closet_mode": "Sample closet",
        }
    ]

    updated_profiles, status, profile_update = remove_saved_profile(
        "M | $35 | Straight jeans + loafers | Sample closet",
        profiles,
    )

    assert updated_profiles == []
    assert "None yet" in status
    assert profile_update["choices"] == []
    assert profile_update["value"] is None


def test_preview_comparable_item_changes_preview_before_history_commit():
    preview = handle_query(
        "preppy striped rugby polo",
        "M",
        35,
        "Straight jeans + loafers",
        "Sample closet",
    )
    choices_update = preview[5]
    comparable_choice = next(choice for choice in choices_update["choices"] if "Leather Belt" in choice)
    comparable_preview = preview_comparable_item(comparable_choice, preview[4])
    rows, _ = add_preview_to_history(comparable_preview[4], [])
    _, profiles, _, _ = save_profiles_from_history(rows, [])

    assert "Leather Belt" in comparable_preview[0]
    assert "Leather Belt" in rows[0][7]
    assert profiles == []

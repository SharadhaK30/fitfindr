"""Data loading helpers for FitFindr.

The assignment asks tools to use these helpers instead of reopening the JSON
files directly. Keeping that boundary also makes tests simple and predictable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_listings() -> list[dict[str, Any]]:
    """Load mock secondhand listings from disk."""
    with (DATA_DIR / "listings.json").open("r", encoding="utf-8") as file:
        return json.load(file)


def get_example_wardrobe() -> dict[str, list[dict[str, Any]]]:
    """Return a small realistic wardrobe for happy-path agent tests."""
    return {
        "items": [
            {
                "id": "wardrobe-jeans-01",
                "name": "baggy light-wash jeans",
                "category": "bottoms",
                "colors": ["light blue"],
                "style_tags": ["denim", "casual", "streetwear"],
                "notes": "High-waisted, loose through the leg.",
            },
            {
                "id": "wardrobe-shoes-01",
                "name": "chunky black sneakers",
                "category": "shoes",
                "colors": ["black", "white"],
                "style_tags": ["chunky", "streetwear", "casual"],
                "notes": "Everyday sneakers with a thick sole.",
            },
            {
                "id": "wardrobe-layer-01",
                "name": "oversized black blazer",
                "category": "outerwear",
                "colors": ["black"],
                "style_tags": ["oversized", "minimal", "layering"],
                "notes": "Structured but roomy enough for layering.",
            },
            {
                "id": "wardrobe-bag-01",
                "name": "small silver shoulder bag",
                "category": "accessories",
                "colors": ["silver"],
                "style_tags": ["90s", "statement", "night out"],
                "notes": "Good when an outfit needs shine.",
            },
        ]
    }


def get_empty_wardrobe() -> dict[str, list[dict[str, Any]]]:
    """Return an empty wardrobe for failure-mode tests."""
    return {"items": []}

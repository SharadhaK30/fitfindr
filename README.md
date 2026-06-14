# FitFindr

FitFindr is a small multi-tool AI agent for secondhand shopping. It searches mock thrift listings, styles the selected item with a user's wardrobe, and creates a short shareable outfit caption while keeping session state visible.

## Setup

```bash
cd fitfindr
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional LLM support uses Groq:

```bash
GROQ_API_KEY=your_key_here
```

Without a Groq key, FitFindr uses local fallback text generation so tests and demos still run.

## Run

```bash
python app.py
```

Or test the planner directly:

```bash
python agent.py
```

## Interface

The Gradio UI includes separate controls for item description, size, max price, and "I mostly wear" styling preferences. The closet selector uses clearer labels: `Sample closet` for the built-in example wardrobe and `No closet items` for empty-wardrobe testing. Marketplace names such as Depop, Poshmark, Gem, and ThredUp are mock resale sources from the sample dataset.

Results appear as garment-specific visual cards with SVG shirt/dress/jacket/shoe/bag previews, color swatches, price checks, an outfit recipe, a shareable fit-token card, and an agent trace panel. The selected listing card includes a price-comparison strip with the selected price, comparable average, similar listing mini-cards, and dot indicators under the strip. A separate `Price item to preview` selector lets the user choose one of those comparable listings and preview it before committing anything to the history table.

Each run can be saved in a spreadsheet-style conversation history table by clicking `Add current fit to history`. This prevents the grid from filling until the user has selected the item they actually want to keep.

## Tool Inventory

`search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Searches `data/listings.json` using title, description, category, tags, colors, brand, exact size, and max price. It returns relevance-sorted listing dictionaries. If nothing matches or data loading fails, it returns `[]`.

`suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Builds a complete outfit suggestion from the selected listing and a wardrobe dictionary with an `items` list. It calls Groq when configured and otherwise uses local styling logic. If the wardrobe is empty, it returns practical advice using common closet basics.

`create_fit_card(outfit: str, new_item: dict) -> str`

Creates a short caption-style fit card from the outfit suggestion and selected listing. It calls Groq when configured and otherwise picks from local caption templates. If the outfit string is empty, it returns a clear error string instead of crashing.

`compare_price(new_item: dict) -> dict`

Stretch tool. Compares the selected listing to similar listings in `data/listings.json`, using same category, overlapping style tags, and size/tag overlap. It returns a dictionary with `assessment`, `item_price`, `average_comparable_price`, `comparable_count`, `comparable_titles`, and `reasoning`. If there are no comparables or the listing is missing, it returns `assessment="unknown"` with an actionable reason.

`get_trend_awareness(new_item: dict, size: str | None = None) -> dict`

Stretch tool. Looks up a mock recent resale-tag trend snapshot based on the selected item's category and optional size. It returns a dictionary with `source`, `trend_tags`, `styling_tip`, and `reasoning`. The planner appends the `styling_tip` to the outfit suggestion so the trend context visibly changes the recommendation.

## Planning Loop

`run_agent()` stores all work in a `session` dictionary and advances through a `next_step` loop. It starts with search, checks the returned listings, and only moves to outfit generation when a selected item exists.

If search returns no listings and a size was provided, the agent retries once without the size filter and records that branch in `session["trace"]`. If the retry also fails, it sets `session["error"]` and returns early, so downstream tools are not called with empty input. On success, the top listing is stored as `session["selected_item"]`, passed to `compare_price()`, passed to `get_trend_awareness()`, then passed to `suggest_outfit()`. The planner appends the trend styling tip to the outfit, stores it as `session["outfit_suggestion"]`, and finally passes both the outfit and selected item to `create_fit_card()`.

## State Management

The session dictionary contains:

- `search_params`: parsed description, size, and max price.
- `listings`: all matching listings returned by search.
- `selected_item`: the top listing dictionary used by downstream tools.
- `price_assessment`: the dictionary returned by `compare_price()`.
- `trend_context`: the dictionary returned by `get_trend_awareness()`.
- `outfit_suggestion`: the string returned by `suggest_outfit()`.
- `fit_card`: the string returned by `create_fit_card()`.
- `error`: a user-facing failure message, or `None`.
- `trace`: a readable log of tool calls and branches.

This makes state passing easy to show in a demo because the same selected listing object moves from search to outfit to fit card without the user re-entering it.

The Gradio UI also stores `profile_memory_state`, which remembers up to three reusable shopping profiles inside the current browser session. A profile contains size, max price, "I mostly wear" style, and closet profile. It does not save the searched item, because the item should stay new for each search. Users save a profile by previewing a fit, clicking `Add current fit to history`, and then checking the `Save` checkbox on that row in the history grid. The saved profile then appears in the `Saved profile memory` dropdown as a short label such as `M | $35 | Straight jeans + loafers | Sample closet`. Choosing that label and clicking `Apply saved profile` fills the size, price, style, and closet fields without re-entry. Clicking `Remove saved profile` deletes the selected profile from memory and updates the dropdown.

## Error Handling

- No search results: `search_listings()` returns `[]`. The agent retries without size when possible, then tells the user to broaden the item description, raise max price, or leave size blank.
- Empty wardrobe: `suggest_outfit()` returns general styling advice using common basics, and the agent still creates a fit card.
- Missing selected item: `suggest_outfit()` returns an explanatory string, while the planner normally prevents the bad call by stopping first.
- Empty outfit: `create_fit_card()` returns `"I need an outfit suggestion before I can write a fit card."`
- Missing or incomparable price input: `compare_price()` returns `assessment="unknown"` and explains whether the selected listing is missing, comparables cannot be loaded, or no similar listings exist.
- Missing trend input: `get_trend_awareness()` returns an empty tag list and explains that a selected listing is needed before trend context can be checked.
- LLM/API failure: Groq calls are wrapped in a fallback path, so the agent still returns useful local output.

Example tested failure:

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```

Expected output: `[]`

## Spec Reflection

The spec helped most by forcing the planning loop to describe actual branches before implementation. That made the no-results path clear: search failure should stop the workflow instead of producing fake outfit text.

One implementation detail diverged from the basic required path: I added a small retry fallback that removes the size filter when search fails. The assignment listed this as a stretch option, and it makes the agent more useful while still preserving the required early-stop behavior when the retry also fails.

## Stretch Features

Price comparison: `compare_price()` estimates whether the selected item is a good deal, fair, or pricey. It builds comparables from the mock dataset by matching same-category listings, listings with at least two shared style tags, or same-size listings with shared tags. The Gradio listing panel displays the assessment and reasoning.

Style profile memory: the Gradio app stores up to three reusable profiles in `profile_memory_state`. A second interaction can choose a saved short label from `Saved profile memory` and click `Apply saved profile`, and the app fills the prior size, max price, "I mostly wear" value, and closet profile without the user typing them again. Users can also remove the selected saved profile. The memory is created from the per-row `Save` checkbox in the history grid, so it is tied to an actual run that the user chose to keep.

Trend awareness: `get_trend_awareness()` uses a local mock trend snapshot based on public fashion-platform style tags, such as rugby stripes, faded graphics, 90s slips, and chunky soles. The trend result is displayed in the outfit card and its styling tip is appended to the outfit suggestion.

Retry logic with fallback: when `search_listings()` returns no results and a size was provided, `run_agent()` automatically retries with `size=None`, records the adjustment in `trace`, and still stops with a specific message if the looser search fails.

## AI Usage

1. I used the assignment requirements and the planned Tool sections as input to generate the first implementation of the three functions in `tools.py`. I revised the search scoring and added local fallbacks so the code works even when Groq is not configured.
2. I used the Planning Loop and Architecture sections as input to implement `run_agent()`. I checked the result against the spec and kept the early-return branch for empty search results, plus a visible `trace` list for demo narration.
3. I used the Stretch Features rubric as input to add the price comparison tool. I reviewed the generated comparison rules and kept them dataset-based rather than using an LLM so the result is explainable and testable.
4. I used the UI and bonus-feature feedback as input to redesign the Gradio app with filters, garment previews, profile memory, trend notes, and a spreadsheet-style history table. I revised the labels to avoid confusing terms like "empty wardrobe" and documented mock marketplaces clearly.

## Tests

```bash
pytest tests/
```

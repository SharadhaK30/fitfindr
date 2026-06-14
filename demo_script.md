# FitFindr Demo Script

Use this as a 3-5 minute narration guide.

## 1. Start the app

```bash
cd /Users/sharadhakasiviswanathan/Downloads/bla/fitfindr
source .venv/bin/activate
python app.py
```

Open the local URL printed by Gradio.

## 2. Happy path

Query:

```text
I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers.
```

Narration:

- Click a starter-search chip first to show the predefined suggestions, or paste the query manually.
- FitFindr parses the description, size, and max price from the user query.
- The planning loop calls `search_listings()` first because no selected item exists yet.
- The selected listing is stored in `session["selected_item"]`.
- The planner passes that same listing to `compare_price()` to assess whether the price is a good deal, fair, or pricey.
- The planner passes that same listing plus the wardrobe to `suggest_outfit()`.
- The planner stores the outfit in `session["outfit_suggestion"]`.
- The planner passes the outfit and listing into `create_fit_card()`.
- Point to the Agent steps panel to show state passing through the tools.
- Point to the listing panel's Price check line for the stretch feature.
- Use the `Price item to preview` selector to choose a comparable item, click `Preview selected price item`, and show that the listing/outfit/fit token update before the history grid changes.
- Point to the Trend cue in the outfit card to show trend awareness visibly influencing the suggestion.
- Point to the fit token card as the shareable final output.
- Click `Add current fit to history`, then point to the conversation history table and note that it records selected item, selected price, price check, fit card, and status.

## 3. Style memory path

Choose `Size = S`, `Max price = $25`, `I mostly wear = Black basics + boots`, and `Closet profile = Sample closet`. Run a search, click `Add current fit to history`, then check `Save` on that row in the history grid. Hover the `i` icon to show the saved memory list. Save one or two more profiles if desired, then select one from `Saved profile memory` and click `Apply saved profile`.

Narration:

- The app saves up to three shopping profiles in session memory.
- Each profile stores size, max price, mostly-wear style, and closet profile. It does not save the searched item, so the next search can still be a new item.
- The per-row Save checkbox saves that specific history row as a profile.
- The hover pop-up shows the saved short labels.
- Applying a saved profile fills the size, price, style, and closet fields without re-entering them.
- `Remove saved profile` deletes the selected saved profile from the dropdown.

## 4. Failure path

Query:

```text
designer ballgown under $5 size XXS
```

Narration:

- Search returns no matches.
- Because a size filter was used, FitFindr retries once without size.
- The retry also returns no matches.
- The agent sets `session["error"]` and stops early.
- The trace shows that `compare_price()`, `get_trend_awareness()`, `suggest_outfit()`, and `create_fit_card()` were not called.

## 5. Optional empty closet check

Run the happy-path query again, but switch Closet profile to `No closet items`.

Narration:

- `suggest_outfit()` handles an empty wardrobe by giving general closet-basics advice.
- The agent still creates a fit card because the outfit tool returned a useful string.

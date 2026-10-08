# xedge-media

Public images for xEdge's social posts. Buffer only accepts images by public link, so every card a post uses is saved here and linked from its raw GitHub address. Nothing here is a post on its own; xEdge's founder approves every post in Buffer before it goes out.

## What's here

- `cards/YYYY-MM-DD/` holds the cards made on that date, such as `margin-watch-feed.jpg` (1080×1350, for the Instagram feed and X) and `margin-watch-story.jpg` (1080×1920, for Instagram Stories).
- `tools/render_margin_watch.py` makes the Margin Watch cards from a JSON file of figures. It refuses to render if a figure fails its sanity checks (margins between 2% and 15%, at least 10 bookmakers per match, rows in margin order).
- `brand/` holds the xEdge logo for dark backgrounds. Never retype the wordmark; always use this file.
- `fonts/` holds Archivo and Geist Mono, both under the SIL Open Font License (see the licence files).

## Making a Margin Watch card

```
python3 tools/render_margin_watch.py /path/outside/repo/figures.json cards/2026-10-09
```

It prints the two file paths and the image's alt text. The figures JSON stays out of this repo.

## Rules for this repo

- Keep it to finished images, the card tools and brand files. No raw odds, price snapshots or figure files: The Odds API's terms don't allow redistributing its data as downloadable files.
- Never name a bookmaker on a card. Every card about prices says 18+ and gives the National Gambling Helpline, 0808 8020 133.
- Don't delete or rename a card after a post uses it. Buffer fetches the image when the post publishes, so the link has to keep working.

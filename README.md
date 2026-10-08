# xedge-media

Public images and videos for xEdge's social posts. Buffer only accepts media by public link, so every card and video a post uses is saved here and linked from its raw GitHub address. Nothing here is a post on its own; xEdge's founder approves every post in Buffer before it goes out.

## What's here

- `cards/YYYY-MM-DD/` holds the cards made on that date, such as `margin-watch-feed.jpg` (1080×1350, for the Instagram feed and X) and `margin-watch-story.jpg` (1080×1920, for Instagram Stories).
- `tools/render_margin_watch.py` makes the Margin Watch cards from a JSON file of figures. It refuses to render if a figure fails its sanity checks (margins between 2% and 15%, at least 10 bookmakers per match, rows in margin order).
- `tools/render_carousel.py` makes Instagram carousel slides (1080×1350) from a JSON file of slides, such as `start-here-01.jpg` to `start-here-05.jpg`. It refuses to render if a slide is too long, names a bookmaker, uses banned wording or would overwrite an existing file.
- `videos/YYYY-MM-DD/` holds the finished explainer videos for TikTok, Reels and Shorts (1080×1920 MP4 with the voiceover) and a cover frame for each.
- `tools/render_video.py` makes those videos from a JSON file of scenes: animated in xEdge's style in code, voiced by ElevenLabs, with captions timed to the voice. It uses the same wording rules as the carousel tool, and its margin checker scene uses the same maths as the free checker on xedge.live.
- `brand/` holds the xEdge logo for dark backgrounds. Never retype the wordmark; always use this file.
- `fonts/` holds Archivo and Geist Mono, both under the SIL Open Font License (see the licence files).

## Making a Margin Watch card

```
python3 tools/render_margin_watch.py /path/outside/repo/figures.json cards/2026-10-09
```

It prints the two file paths and the image's alt text. The figures JSON stays out of this repo.

## Making a carousel

```
python3 tools/render_carousel.py /path/outside/repo/slides.json cards/2026-10-12 --name odds-are-chances
```

The slide types (cover, text, number, list and end) and the JSON format are described at the top of the script. Every slide gets the 18+ badge and the helpline, and the end slide adds xedge.live. It prints the file paths, each slide's alt text and any wording a person should double-check against the Rules tab.

## Making a video

```
python3 tools/render_video.py /path/outside/repo/scenes.json videos/2026-10-11 --name the-4-8-you-never-see --work /path/outside/repo/work
```

The scene types (hook, text, prices, sum, number, compare, list, checker and end) and the JSON format are described at the top of the script. Every frame shows 18+ and the helpline, and the end card adds xedge.live and the full National Gambling Helpline line. Add `--preview` for a silent draft with guessed timings, or `--stills 1.5,9,20` to look at single frames; both write only into the work folder.

The voice comes from ElevenLabs. Its API key is stored as an API credential on the Claude cloud environment, for `api.elevenlabs.io`, so it is never in this repo, a file or a command. Voice clips are cached in the work folder, so a re-render costs no credits. A 30-second video uses about 400 characters of voice.

## Rules for this repo

- Keep it to finished images and videos, the tools that make them and brand files. No raw odds, price snapshots or figure files: The Odds API's terms don't allow redistributing its data as downloadable files.
- Never name a bookmaker on a card or in a video. Every card and video about prices says 18+ and gives the National Gambling Helpline, 0808 8020 133.
- Don't delete or rename a card or video after a post uses it. Buffer fetches the file when the post publishes, so the link has to keep working.

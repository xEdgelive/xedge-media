#!/usr/bin/env python3
"""Render an xEdge explainer video (1080x1920, 30 fps H.264 MP4 with AAC voice) from a JSON file of scenes.

Usage:
  python3 tools/render_video.py spec.json videos/YYYY-MM-DD --name the-4-8-you-never-see --work /path/outside/repo
  python3 tools/render_video.py spec.json videos/YYYY-MM-DD --name the-4-8-you-never-see --work /path/outside/repo --preview

The voiceover comes from ElevenLabs' text-to-speech API as one continuous take of the whole
script (Chris on Eleven v4 by default), timed to the word so captions and animation follow it.
The API key is never in this repo, a file or the command line: the cloud environment's API
credential adds it to requests for api.elevenlabs.io. The take is cached in --work, so a
re-render costs no credits. --preview skips the voice, guesses the timings and writes a silent
preview into --work only.

spec.json (keep it outside this repo):
{
  "voice": {"voice_id": "HfRP3cIhYLmeNHeTvkWK", "model_id": "eleven_v4", "tempo": 1.0},   (optional)
  "scenes": [
    {"type": "hook", "kicker": "PRICE CHECK", "title": "Every match has a [[hidden fee]]",
     "say": "Every football match has a hidden fee."},
    {"type": "prices", "kicker": "ONE MATCH'S ODDS · EXAMPLE", "to_kicker": "AS A CHANCE",
     "tiles": [{"label": "HOME", "value": "11/10", "sub": "2.10", "to": "47.6%", "to_sub": "1 ÷ 2.10"}, ...],
     "say": "These are one match's odds: {1}[11/10|eleven to ten], {2}[12/5|twelve to five] and {3}[13/5|thirteen to five]. As chances, that's {4}47.6, {5}29.4 and {6}27.8%."},
    {"type": "sum", "kicker": "ADD THEM UP", "values": ["47.6%", "29.4%", "27.8%"], "total": "104.8%",
     "say": "Add them up and you get {1}104.8. {2}A fair book adds up to 100."},
    {"type": "number", "number": "4.8%", "title": "The bookmaker's margin", "body": "Built into every price", "say": "..."},
    {"type": "compare", "kicker": "...", "bars": [{"label": "Your chance", "value": "55%"}, {"label": "Price needs", "value": "60%", "hi": true}], "say": "..."},
    {"type": "list", "title": "...", "items": ["...", "..."], "say": "{1}... {2}..."},
    {"type": "text", "kicker": "...", "title": "...", "body": "...", "say": "..."},
    {"type": "checker", "odds": ["2.10", "3.40", "3.60"], "say": "Check any match with the free margin checker at [xedge.live|ex edge dot live]."},
    {"type": "end", "title": "Check any match free"}
  ]
}

A queue entry from the private repo xEdgelive/xedge-queue, {"name", "folder", "buffer_drafts", "caption",
"slot", "scenes"}, can be passed as it is. "slot" (mon to sun) is the day of the folder's week the video goes
out; the video routine uses it to schedule the posts, and the tool only checks it's a weekday. The tool checks that its name and folder match --name and the output
folder, and holds its caption to the same wording rules as the scenes (and it must say 18+).

- 3 to 9 scenes. The first must be a hook and the last an end card. Every scene but the end card has a voice line.
- In "say", [shown|spoken] puts one thing in the captions and has the voice say another (fractional
  odds, the web address). {1}, {2} ... mark the moments the animation steps forward: tiles
  appearing then converting, a total landing, bars growing, list items appearing. A prices scene
  whose tiles convert needs a beat as each tile appears and another as each one converts: {1} to
  {6} for three tiles, {1} to {4} for two. A tile without its converting beat never converts, so the
  tool refuses a prices scene that's short of beats.
- Write numbers as digits ("47.6", "104.8%"); Eleven v4 reads them naturally. Fractional odds and the
  web address still need [shown|spoken]: [11/10|eleven to ten], [xedge.live|ex edge dot live].
- [[Double brackets]] in a title show those words in the brand colour.
- The checker scene is a copy of the free margin checker on xedge.live, with the same maths
  (the power method), so whatever odds it types give the numbers the real checker shows.
- Every frame carries 18+, and the end card adds xedge.live and its own 18+ line. Since 22 Oct 2026
  the videos carry no helpline (Adam's decision); it stays in the bios and on the website.

Football scenes (added 13 Nov 2026 with the creative upgrade): a moving football picture under the hook, and
four scene types drawn on a dark xEdge pitch. Old scene files don't use them, so they render exactly as before.
FOOTBALL_SCENES below switches all of them off at once; the checker then refuses them.
    {"type": "hook", "title": "Same match. Why [[two prices?]]", "say": "...", "visual": "pitch"},
    {"type": "pitch_story", "kicker": "ILLUSTRATION · ONE ATTACK", "title": "One chance. [[Two outcomes.]]",
     "pitch_view": "half", "players": [{"side": "home", "x": 0.3, "y": 0.4}, {"side": "away", "x": 0.6, "y": 0.55}],
     "ball_path": [[0.3, 0.4], [0.62, 0.7], [0.99, 0.48]], "focus": "ball",
     "say": "A pass{1} out wide, then a shot{2} into the corner."},
    {"type": "match_compare", "kicker": "ONE OUTCOME · EXAMPLE", "title": "Same match. [[Two prices.]]",
     "outcome": "Home win", "offers": [{"label": "A", "decimal_odds": 2.50}, {"label": "B", "decimal_odds": 2.75}],
     "say": "One price{1} is 2.50, another{2} is 2.75. As chances{3}, that's 40 and 36.4%.{4} A 3.6 point gap."},
    {"type": "probability_pitch", "kicker": "A ONE IN FIVE CHANCE", "title": "A chance [[isn't a goal]]",
     "probability": 0.2, "trials": 10, "say": "Give ten shots{1} a one in five chance each.{2} About two go in."},
    {"type": "football_stat", "kicker": "SAMPLE SIZE", "title": "60% [[of what?]]", "numerator": 6,
     "denominator": 10, "of_what": "matches", "say": "Six{1} out of ten matches{2} is 60%. Ten is a small sample."},
- "visual" on the hook (optional): "pitch" (the attacking third of a pitch, a passing move drawing a lime trail)
  or "goal" (a goal seen from the front, a shot flying at it). It moves from the first frame, under the title,
  and shows on the cover. Leave it out for the plain hook.
- pitch_story is always tagged ILLUSTRATION: never a real match, real players or tracking data. pitch_view "half"
  (the default) is the attacking half upright, goal at the top: x 0 is the halfway line and 1 the goal line, y 0 the
  left touchline and 1 the right. "full" is the whole pitch on its side: x 0 the left goal line and 1 the goal
  attacked on the right, y 0 the top touchline and 1 the bottom. Every coordinate is 0 to 1. players: up to 22
  markers, "home" solid or "away" ringed, each with an optional "id" (up to 4 lowercase letters or digits, unique).
  ball_path: 2 to 16 points, each at least half a metre from the one before; the ball travels it pass by pass and
  leaves a lime trail. {1}, {2} ... start each pass; without them the passes follow one another. Put the last beat
  a second or more before the line ends: the ball always arrives before the scene moves on, so a late last pass
  is rushed. A path ending in
  the goal mouth ("half": x 0.99 or more; "full": 0.995 or more; y 0.447 to 0.553) lights the net. focus: "ball"
  (the camera follows the ball; the default), "goal" (it eases towards the goal) or "none" (it stays still).
- match_compare puts 2 or 3 prices for one outcome side by side, turns each into its raw implied chance (100 ÷ decimal
  odds, worked out here: 2.50 shows 40.0%, 2.75 shows 36.4%) and shows the gap between the highest and lowest in
  percentage points (3.6, worked out from the unrounded chances). It's labelled raw implied, never fair: the
  bookmaker's margin is still in it. Prices are decimal numbers from 1.01 to 100 with at most 2 decimal places, all
  different; labels up to 8 characters (never a bookmaker's name). {1} to {n} bring in each price, {n+1} turns them
  into chances, {n+2} shows the gap. "source_status" is "example" (the default: labelled EXAMPLE PRICES, the match
  shown as EXAMPLE MATCH unless "match_label" says otherwise) or "real", which needs "match_label", "source" and
  "date" (YYYY-MM-DD) and shows them.
- probability_pitch fires "trials" shots (2 to 20) at a goal, each with chance "probability" (between 0 and 1).
  Exactly probability × trials of them go in, so that must be a whole number (0.2 × 10 = 2). It's always tagged
  TOY EXAMPLE, NOT REAL DATA. {1} starts the shots, {2} shows the split (20% goal, 80% no goal).
- football_stat shows numerator ÷ denominator as a percentage (worked out here; "decimals" 0, the default, or 1) above
  a grid of that many small pitches with numerator of them lit, and "6 OF 10 MATCHES". denominator 1 to 100;
  of_what is the plural noun (up to 20 characters). "source_status" is "example" (the default, tagged EXAMPLE, NOT
  REAL DATA) or "real", which needs "source", "date" (YYYY-MM-DD), "competition", "window" (the period counted) and
  "definition" (what was counted), all shown. {1} brings in the grid, {2} lights the matches.
- In every football scene, the figures on screen are worked out by this tool from the numbers given; write the
  voice line to match them (40 and 36.4, not 40 and 36).

It refuses to render if text is too long or doesn't fit, names a bookmaker, uses banned
wording, or would overwrite a video a post may be using. Softer wording matches are printed
as warnings for a person to check against the Rules tab.
"""
import argparse
import datetime
import decimal
import hashlib
import html
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import base64
import urllib.error
import urllib.request
import wave

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_carousel import BANNED, BOOKMAKERS, WARN  # noqa: E402  (same wording rules as the cards)

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H, FPS, SR = 1080, 1920, 30, 48000
# Where there's no Playwright browser or system ffmpeg (a fresh cloud environment), point these at
# a Chrome / chrome-headless-shell binary and an ffmpeg binary.
CHROMIUM = os.environ.get("XEDGE_CHROMIUM") or None


def ffmpeg_bin() -> str:
    found = os.environ.get("XEDGE_FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: install it (apt-get install -y ffmpeg, or pip install imageio-ffmpeg) or set XEDGE_FFMPEG")

# Chris (casual, conversational, clearly adult British voice) on Eleven v4, ElevenLabs' most natural model.
# Eleven v4 has no speed or style setting; "tempo" speeds the finished take up or down (1.0 = as spoken).
DEFAULT_VOICE = {"voice_id": "HfRP3cIhYLmeNHeTvkWK", "model_id": "eleven_v4", "speed": 1.0,
                 "stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "tempo": 1.0}
V2_MODELS = {"eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"}
LEAD, PRE, END_GAP, END_HOLD = 0.2, 0.12, 0.45, 2.0

LIMITS = {
    "hook": {"kicker": 32, "title": 48, "say": 160},
    "text": {"kicker": 32, "title": 60, "body": 110, "say": 260},
    "prices": {"kicker": 32, "to_kicker": 32, "say": 300},
    "sum": {"kicker": 32, "total": 8, "say": 220},
    "number": {"kicker": 32, "number": 7, "title": 50, "body": 90, "say": 260},
    "compare": {"kicker": 32, "title": 50, "say": 260},
    "list": {"kicker": 32, "title": 50, "say": 300},
    "checker": {"say": 200},
    "end": {"title": 40, "body": 80},
}
REQUIRED = {"hook": ["title", "say"], "text": ["title", "say"], "prices": ["tiles", "say"], "sum": ["values", "total", "say"],
            "number": ["number", "title", "say"], "compare": ["bars", "say"], "list": ["title", "items", "say"],
            "checker": ["odds", "say"], "end": ["title"]}
EXTRA_KEYS = {"prices": {"tiles"}, "sum": {"values"}, "compare": {"bars"}, "list": {"items"}, "checker": {"odds"}}
TOKEN = re.compile(r"\{(\d)\}|\[([^\[\]|]+)\|([^\[\]|]+)\]")

# Football scenes (the creative upgrade, 13 Nov 2026). They're opt-in: a scene file only gets them by asking for one
# of these types, or a hook "visual". False switches them all off; the checker then refuses them, and nothing else
# changes.
FOOTBALL_SCENES = True
FOOTBALL_KINDS = ("pitch_story", "match_compare", "probability_pitch", "football_stat")
HOOK_VISUALS = ("pitch", "goal")
LIMITS.update({
    "pitch_story": {"kicker": 32, "title": 50, "say": 300},
    "match_compare": {"kicker": 32, "title": 50, "match_label": 28, "outcome": 18, "source": 40, "date": 10, "say": 300},
    "probability_pitch": {"kicker": 32, "title": 50, "say": 300},
    "football_stat": {"kicker": 32, "title": 50, "of_what": 20, "source": 40, "date": 10, "competition": 30,
                      "window": 30, "definition": 60, "say": 300},
})
# Numbers (probability, trials, numerator, denominator) are checked as numbers below, not here: 0 is a real value.
REQUIRED.update({"pitch_story": ["title", "ball_path", "say"], "match_compare": ["title", "outcome", "offers", "say"],
                 "probability_pitch": ["title", "say"], "football_stat": ["title", "of_what", "say"]})
EXTRA_KEYS.update({"hook": {"visual"}, "pitch_story": {"pitch_view", "players", "ball_path", "focus"},
                   "match_compare": {"offers", "source_status"}, "probability_pitch": {"probability", "trials"},
                   "football_stat": {"numerator", "denominator", "decimals", "source_status"}})


# ---------------------------------------------------------------- checks

def parse_say(say: str) -> dict:
    """Split a say line into the spoken text, the caption words and the beat positions."""
    spoken, display, spans, beats = [], [], [], {}
    pos = 0

    def plain(text):
        for ch in text:
            spans.append((len(spoken), len(spoken) + 1))
            display.append(ch)
            spoken.append(ch)

    for m in TOKEN.finditer(say):
        plain(say[pos:m.start()])
        if m.group(1):
            beats[int(m.group(1))] = len(spoken)
        else:
            shown, said = m.group(2), m.group(3)
            a = len(spoken)
            spoken.extend(said)
            for ch in shown:
                spans.append((a, len(spoken)))
                display.append(ch)
        pos = m.end()
    plain(say[pos:])
    d, s = "".join(display), "".join(spoken)
    words = []
    for m in re.finditer(r"\S+", d):
        a = min(spans[i][0] for i in range(m.start(), m.end()))
        b = max(spans[i][1] for i in range(m.start(), m.end()))
        words.append({"w": m.group(0), "a": a, "b": b})
    return {"spoken": s, "display": d, "words": words, "beats": beats}


def plain(text: str) -> str:
    return re.sub(r"\[\[(.+?)\]\]", r"\1", text)


def texts_in(sc: dict) -> list:
    out = [str(sc.get(k, "")) for k in ("kicker", "to_kicker", "title", "body", "number", "total")]
    for t in sc.get("tiles", []) or []:
        out += [str(t.get(k, "")) for k in ("label", "value", "sub", "to", "to_sub")]
    out += [str(v) for v in sc.get("values", []) or []]
    out += [str(i) for i in sc.get("items", []) or []]
    for b in sc.get("bars", []) or []:
        out += [str(b.get("label", "")), str(b.get("value", ""))]
    if sc.get("type") in FOOTBALL_KINDS:
        out += [str(sc.get(k, "")) for k in ("match_label", "outcome", "of_what", "source", "competition", "window",
                                             "definition")]
        offers = sc.get("offers")
        for o in offers if isinstance(offers, list) else []:
            if isinstance(o, dict):
                out.append(str(o.get("label", "")))
    if sc.get("say"):
        p = parse_say(sc["say"])
        out += [p["display"], p["spoken"]]
    return out


def odds_value(text: str) -> float:
    text = str(text).strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if m:
        return 1 + float(m.group(1)) / float(m.group(2))
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    raise ValueError(text)


# A queue entry from the private repo xEdgelive/xedge-queue can be passed as it is: these fields
# are for the routine that makes the video, and the tool only checks them.
QUEUE_KEYS = {"name", "folder", "buffer_drafts", "caption", "slot", "result"}
SLOTS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def check(d: dict) -> tuple:
    problems, warnings = [], []
    scenes = d.get("scenes")
    if not isinstance(scenes, list) or not 3 <= len(scenes) <= 9:
        return ["there must be 3 to 9 scenes"], warnings
    if not isinstance(scenes[0], dict) or scenes[0].get("type") != "hook":
        problems.append("scene 1 must be a hook")
    if not isinstance(scenes[-1], dict) or scenes[-1].get("type") != "end":
        problems.append(f"scene {len(scenes)} must be an end card")
    voice = d.get("voice", {})
    if not isinstance(voice, dict) or set(voice) - set(DEFAULT_VOICE):
        problems.append(f"voice can only set {', '.join(DEFAULT_VOICE)}")
    for k in set(d) - {"voice", "scenes"} - QUEUE_KEYS:
        problems.append(f"{k!r} isn't used")
    if "name" in d and not (isinstance(d["name"], str) and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", d["name"])):
        problems.append("name must be lowercase letters, digits and hyphens")
    if "folder" in d and not (isinstance(d["folder"], str) and re.fullmatch(r"videos/\d{4}-\d{2}-\d{2}", d["folder"])):
        problems.append("folder must look like videos/YYYY-MM-DD")
    if "buffer_drafts" in d and not isinstance(d["buffer_drafts"], bool):
        problems.append("buffer_drafts must be true or false")
    if "slot" in d and d["slot"] not in SLOTS:
        problems.append("slot must be a weekday: mon, tue, wed, thu, fri, sat or sun")
    if "caption" in d:
        cap = d["caption"]
        if not isinstance(cap, str) or not cap.strip():
            problems.append("caption must be text")
        else:
            if len(cap) > 2200:
                problems.append("caption is over 2,200 characters, TikTok's and Instagram's limit")
            if "18+" not in cap:
                problems.append("caption must say 18+")
            text = cap.lower().replace("’", "'").replace("‘", "'")
            for name in BOOKMAKERS:
                if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                    problems.append(f"caption names a bookmaker ({name})")
            for pattern in BANNED:
                m = re.search(rf"\b{pattern}\b", text)
                if m:
                    problems.append(f"caption: banned wording ({m.group(0)!r})")
            for pattern in WARN:
                m = re.search(rf"\b{pattern}\b", text)
                if m:
                    warnings.append(f"caption: check the context of {m.group(0)!r}")
    for n, sc in enumerate(scenes, 1):
        if not isinstance(sc, dict):
            problems.append(f"scene {n}: not a scene object")
            continue
        kind = sc.get("type")
        if kind not in LIMITS:
            problems.append(f"scene {n}: unknown type {kind!r}")
            continue
        if n not in (1, len(scenes)) and kind in ("hook", "end"):
            problems.append(f"scene {n}: a {kind} can only come {'first' if kind == 'hook' else 'last'}")
        for key in REQUIRED[kind]:
            if not sc.get(key):
                problems.append(f"scene {n}: missing {key}")
        allowed = set(LIMITS[kind]) | {"type"} | EXTRA_KEYS.get(kind, set())
        for key in sc:
            if key not in allowed:
                problems.append(f"scene {n}: {key!r} isn't used on a {kind} scene")
        for key, limit in LIMITS[kind].items():
            value = str(sc.get(key, ""))
            size = len(parse_say(value)["display"]) if key == "say" else len(plain(value))
            if size > limit:
                problems.append(f"scene {n}: {key} is {size} characters (limit {limit})")
        if kind == "prices":
            tiles = sc.get("tiles") or []
            if not 2 <= len(tiles) <= 3:
                problems.append(f"scene {n}: 2 or 3 tiles")
            for i, t in enumerate(tiles, 1):
                if not isinstance(t, dict) or not t.get("label") or not t.get("value"):
                    problems.append(f"scene {n}: tile {i} needs a label and a value")
                    continue
                for key, limit in (("label", 8), ("value", 7), ("sub", 12), ("to", 7), ("to_sub", 12)):
                    if len(str(t.get(key, ""))) > limit:
                        problems.append(f"scene {n}: tile {i} {key} is over {limit} characters")
                for key in set(t) - {"label", "value", "sub", "to", "to_sub"}:
                    problems.append(f"scene {n}: tile {i} {key!r} isn't used")
            if len({bool(t.get("to")) for t in tiles if isinstance(t, dict)}) > 1:
                problems.append(f"scene {n}: either every tile converts ('to') or none does")
        if kind == "sum":
            values = sc.get("values") or []
            if not 2 <= len(values) <= 4 or any(len(str(v)) > 7 for v in values):
                problems.append(f"scene {n}: 2 to 4 values of up to 7 characters")
            try:
                parts = [float(re.sub(r"[^\d.]", "", str(v))) for v in values]
                total = float(re.sub(r"[^\d.]", "", str(sc.get("total", ""))))
                if abs(sum(parts) - total) > 0.15:
                    problems.append(f"scene {n}: the values add up to {sum(parts):.1f}, not {sc.get('total')}")
            except ValueError:
                problems.append(f"scene {n}: values and total must be numbers")
        if kind == "compare":
            bars = sc.get("bars") or []
            if not 2 <= len(bars) <= 3:
                problems.append(f"scene {n}: 2 or 3 bars")
            for i, b in enumerate(bars, 1):
                if not isinstance(b, dict) or len(str(b.get("label", ""))) > 24 or not re.fullmatch(r"\d+(\.\d+)?%", str(b.get("value", ""))):
                    problems.append(f"scene {n}: bar {i} needs a label of up to 24 characters and a value like 55%")
                elif set(b) - {"label", "value", "hi"}:
                    problems.append(f"scene {n}: bar {i} has unknown keys")
        if kind == "list":
            items = sc.get("items") or []
            if not 2 <= len(items) <= 4 or any(len(str(i)) > 50 for i in items):
                problems.append(f"scene {n}: 2 to 4 items of up to 50 characters")
        if kind == "checker":
            odds = sc.get("odds") or []
            try:
                if len(odds) != 3 or any(not 1.01 <= odds_value(o) <= 1000 for o in odds):
                    raise ValueError
            except ValueError:
                problems.append(f"scene {n}: checker needs three odds, decimal (2.10) or fractional (11/10)")
        if kind in FOOTBALL_KINDS or (kind == "hook" and "visual" in sc):
            check_football(n, kind, sc, problems)
        if sc.get("say"):
            p = parse_say(sc["say"])
            if re.search(r"[\[\]{}|]", p["display"]):
                problems.append(f"scene {n}: say has a stray bracket or bar; use [shown|spoken] and {{1}}")
            want = {"prices": 2 * len(sc.get("tiles") or []) if any(isinstance(t, dict) and t.get("to") for t in sc.get("tiles") or []) else len(sc.get("tiles") or []),
                    "sum": 2, "compare": len(sc.get("bars") or []), "list": len(sc.get("items") or [])}.get(kind)
            if kind in FOOTBALL_KINDS:
                want = football_beats(kind, sc)
            if p["beats"] and want and sorted(p["beats"]) != list(range(1, len(p["beats"]) + 1)):
                problems.append(f"scene {n}: beats must be numbered {{1}}, {{2}} ... in order")
            if p["beats"] and want and len(p["beats"]) > want:
                problems.append(f"scene {n}: {len(p['beats'])} beats but this scene uses at most {want}")
            converting = [t for t in sc.get("tiles") or [] if isinstance(t, dict) and t.get("to")]
            if kind == "prices" and converting and len(p["beats"]) < want:
                problems.append(f"scene {n}: its {len(converting)} tiles convert, so say needs {{1}} to {{{want}}}: "
                                f"a beat as each tile appears and another as each one converts. It has "
                                f"{len(p['beats'])}, and a tile without its converting beat never converts")
        text = plain(" ".join(texts_in(sc))).lower().replace("’", "'").replace("‘", "'")
        for name in BOOKMAKERS:
            if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                problems.append(f"scene {n}: names a bookmaker ({name})")
        for pattern in BANNED:
            m = re.search(rf"\b{pattern}\b", text)
            if m:
                problems.append(f"scene {n}: banned wording ({m.group(0)!r})")
        for pattern in WARN:
            m = re.search(rf"\b{pattern}\b", text)
            if m:
                warnings.append(f"scene {n}: check the context of {m.group(0)!r}")
    return problems, warnings


# ---------------------------------------------------------------- the margin checker's maths

def checker_numbers(odds: list) -> dict:
    """Same output as xedge.live's margin checker: margin = sum of 1/odds - 1, fair prices by the power method."""
    p = [1 / odds_value(o) for o in odds]
    margin = sum(p) - 1
    lo, hi = 0.2, 5.0
    for _ in range(200):
        k = (lo + hi) / 2
        if sum(x ** k for x in p) > 1:
            lo = k
        else:
            hi = k
    fair = [x ** k for x in p] if margin > 0 else [x / sum(p) for x in p]
    return {"margin": f"{margin * 100:.1f}%", "fair": [f"{1 / q:.2f}" for q in fair],
            "prob": [f"{q * 100:.1f}%" for q in fair], "under": margin <= 0}


# ---------------------------------------------------------------- football scenes

PITCH_L, PITCH_W, GOAL_HALF = 105.0, 68.0, 3.66  # metres: pitch length and width, half the goal's width
PITCH_VIEWBOX = {"half": (-4.0, -4.5, 76.0, 61.5), "full": (-4.5, -4.0, 114.0, 76.0)}
# The hook's "pitch" picture: the attacking third of the half pitch and a fixed passing move.
HOOK_PITCH = {"pitch_view": "half", "focus": "ball",
              "players": [{"side": "home", "x": 0.5, "y": 0.22}, {"side": "home", "x": 0.72, "y": 0.68},
                          {"side": "home", "x": 0.63, "y": 0.42}, {"side": "away", "x": 0.6, "y": 0.56},
                          {"side": "away", "x": 0.8, "y": 0.6}, {"side": "away", "x": 0.85, "y": 0.4},
                          {"side": "away", "x": 0.97, "y": 0.5}],
              "ball_path": [[0.5, 0.22], [0.72, 0.68], [0.9, 0.53]]}
HOOK_PITCH_VIEWBOX = (-4.0, -4.5, 76.0, 34.0)
GOAL_BOX = (140.0, 66.0, 600.0, 200.0)  # probability_pitch: the goal in its 880 x 440 drawing, 600 px for 7.32 m
SHOT_FROM = (440.0, 404.0)
MINI_PITCH = ('<svg class="mini" viewBox="0 0 66 44"><rect x="1.5" y="1.5" width="63" height="41" rx="3"/>'
              '<line x1="33" y1="1.5" x2="33" y2="42.5"/><circle cx="33" cy="22" r="7"/></svg>')


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def valid_date(v) -> bool:
    if not (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)):
        return False
    try:
        datetime.date.fromisoformat(v)
        return True
    except ValueError:
        return False


def pitch_point(view: str, x: float, y: float) -> tuple:
    """A 0-to-1 pitch position as metres in the drawing (pitch_view in the notes at the top says which way up)."""
    if view == "full":
        return (x * PITCH_L, y * PITCH_W)
    return (y * PITCH_W, (1 - x) * PITCH_L / 2)


def path_ok(path) -> bool:
    return (isinstance(path, list) and 2 <= len(path) <= 16 and
            all(isinstance(p, list) and len(p) == 2 and all(is_num(c) and 0 <= c <= 1 for c in p) for p in path))


def check_football(n: int, kind: str, sc: dict, problems: list) -> None:
    """The football scenes' own checks. The shared ones (lengths, wording, beats) run for them as well."""
    if not FOOTBALL_SCENES:
        what = "hook visuals" if kind == "hook" else f"{kind} scenes"
        problems.append(f"scene {n}: {what} are switched off (FOOTBALL_SCENES in tools/render_video.py)")
        return
    if kind == "hook":
        if sc["visual"] not in HOOK_VISUALS:
            problems.append(f'scene {n}: visual must be "pitch" or "goal"')
    elif kind == "pitch_story":
        view = sc.get("pitch_view", "half")
        if view not in ("half", "full"):
            problems.append(f'scene {n}: pitch_view must be "half" or "full"')
            view = "half"
        if sc.get("focus", "ball") not in ("ball", "goal", "none"):
            problems.append(f'scene {n}: focus must be "ball", "goal" or "none"')
        players = sc.get("players", [])
        if not isinstance(players, list) or len(players) > 22:
            problems.append(f"scene {n}: players must be a list of up to 22 markers")
            players = []
        ids = []
        for i, pl in enumerate(players, 1):
            if not isinstance(pl, dict) or set(pl) - {"id", "side", "x", "y"}:
                problems.append(f"scene {n}: player {i} can only have side, x, y and id")
                continue
            if pl.get("side") not in ("home", "away"):
                problems.append(f'scene {n}: player {i} side must be "home" or "away"')
            if not all(is_num(pl.get(c)) and 0 <= pl[c] <= 1 for c in ("x", "y")):
                problems.append(f"scene {n}: player {i} needs x and y, numbers from 0 to 1")
            if "id" in pl:
                if not (isinstance(pl["id"], str) and re.fullmatch(r"[a-z0-9]{1,4}", pl["id"])):
                    problems.append(f"scene {n}: player {i} id must be 1 to 4 lowercase letters or digits")
                ids.append(str(pl["id"]))
        if len(ids) != len(set(ids)):
            problems.append(f"scene {n}: player ids must be different")
        path = sc.get("ball_path")
        if not path_ok(path):
            problems.append(f"scene {n}: ball_path needs 2 to 16 points, each [x, y] with numbers from 0 to 1")
        else:
            pts = [pitch_point(view, *p) for p in path]
            for i, (a, b) in enumerate(zip(pts, pts[1:]), 2):
                if math.dist(a, b) < 0.5:
                    problems.append(f"scene {n}: ball_path point {i} is under half a metre from the one before")
    elif kind == "match_compare":
        offers = sc.get("offers")
        if not isinstance(offers, list) or not 2 <= len(offers) <= 3:
            problems.append(f"scene {n}: match_compare needs 2 or 3 offers")
        else:
            good = []
            for i, o in enumerate(offers, 1):
                if not isinstance(o, dict) or set(o) != {"label", "decimal_odds"}:
                    problems.append(f"scene {n}: offer {i} needs a label and decimal_odds, and nothing else")
                    continue
                if not isinstance(o["label"], str) or not 1 <= len(o["label"].strip()) <= 8:
                    problems.append(f"scene {n}: offer {i} label must be 1 to 8 characters")
                d = o["decimal_odds"]
                if not is_num(d) or not 1.01 <= d <= 100 or abs(round(d, 2) - d) > 1e-9:
                    problems.append(f"scene {n}: offer {i} decimal_odds must be a number from 1.01 to 100 with at most 2 decimal places")
                else:
                    good.append(round(d, 2))
            labels = [str(o.get("label", "")).strip().lower() for o in offers if isinstance(o, dict)]
            if len(set(labels)) != len(labels):
                problems.append(f"scene {n}: offer labels must be different")
            if len(set(good)) != len(good):
                problems.append(f"scene {n}: the offers must have different prices")
        source_rules(n, sc, ("match_label", "source", "date"), problems)
    elif kind == "probability_pitch":
        p, k = sc.get("probability"), sc.get("trials")
        if not (is_num(p) and 0 < p < 1):
            problems.append(f"scene {n}: probability must be a number between 0 and 1, such as 0.2")
        if not (is_int(k) and 2 <= k <= 20):
            problems.append(f"scene {n}: trials must be a whole number from 2 to 20")
        elif is_num(p) and abs(p * k - round(p * k)) > 1e-9:
            problems.append(f"scene {n}: probability × trials must be a whole number ({p:g} × {k} = {p * k:g}), "
                            "so the picture shows exactly that many goals")
    elif kind == "football_stat":
        num, den = sc.get("numerator"), sc.get("denominator")
        if not (is_int(den) and 1 <= den <= 100):
            problems.append(f"scene {n}: denominator must be a whole number from 1 to 100")
        if not (is_int(num) and num >= 0):
            problems.append(f"scene {n}: numerator must be a whole number, 0 or more")
        elif is_int(den) and num > den:
            problems.append(f"scene {n}: numerator can't be more than denominator")
        if "decimals" in sc and not (is_int(sc["decimals"]) and sc["decimals"] in (0, 1)):
            problems.append(f"scene {n}: decimals must be 0 or 1")
        source_rules(n, sc, ("source", "date", "competition", "window", "definition"), problems)


def source_rules(n: int, sc: dict, needed: tuple, problems: list) -> None:
    """Example figures are labelled as examples; real ones must say where they come from."""
    status = sc.get("source_status", "example")
    if status not in ("example", "real"):
        problems.append(f'scene {n}: source_status must be "example" or "real"')
    elif status == "real":
        for key in needed:
            if not sc.get(key):
                problems.append(f'scene {n}: real figures (source_status "real") need {key}')
        if sc.get("date") and not valid_date(sc["date"]):
            problems.append(f"scene {n}: date must be a real date written YYYY-MM-DD")
    else:
        extra = [k for k in needed if k != "match_label" and sc.get(k)]
        if extra:
            problems.append(f'scene {n}: {", ".join(extra)} {"is" if len(extra) == 1 else "are"} only for real '
                            'figures (source_status "real")')


def football_beats(kind: str, sc: dict):
    """How many {1}, {2} ... beats a football scene uses (None when its data is broken: other checks say so)."""
    if kind == "pitch_story":
        return len(sc["ball_path"]) - 1 if path_ok(sc.get("ball_path")) else None
    if kind == "match_compare":
        offers = sc.get("offers")
        return len(offers) + 2 if isinstance(offers, list) and 2 <= len(offers) <= 3 else None
    return 2


def pct_text(value: decimal.Decimal, places: int) -> str:
    """A percentage for the screen, rounded half up only here, at the end."""
    return f"{value.quantize(decimal.Decimal(1).scaleb(-places), rounding=decimal.ROUND_HALF_UP)}%"


def compare_numbers(sc: dict) -> dict:
    """Each price's raw implied chance (100 ÷ decimal odds) and the gap between the highest and lowest chance in
    percentage points, worked out at full precision: 2.50 gives 40.0%, 2.75 gives 36.4% and the gap is 3.6."""
    raws = [decimal.Decimal(100) / decimal.Decimal(f"{o['decimal_odds']:.2f}") for o in sc["offers"]]
    hi = max(range(len(raws)), key=lambda i: raws[i])
    lo = min(range(len(raws)), key=lambda i: raws[i])
    return {"offers": [{"label": o["label"].strip(), "odds": f"{o['decimal_odds']:.2f}", "raw": float(r),
                        "rawText": pct_text(r, 1)} for o, r in zip(sc["offers"], raws)],
            "gap": {"hi": hi, "lo": lo, "text": pct_text(raws[hi] - raws[lo], 1)[:-1]}}


def stat_numbers(sc: dict) -> dict:
    num, den, places = sc["numerator"], sc["denominator"], sc.get("decimals", 0)
    pct = decimal.Decimal(100 * num) / decimal.Decimal(den)
    return {"num": num, "den": den, "pct": float(pct), "dec": places, "text": pct_text(pct, places)}


def stat_grid(den: int, width: float = 880, height: float = 300) -> dict:
    """Columns and size for den small upright pitches, as large as fits in width x height (at most 104 px wide)."""
    best = None
    for cols in range(1, min(den, 25) + 1):
        rows = math.ceil(den / cols)
        gap = 14 if cols <= 10 else 8
        w = min((width - (cols - 1) * gap) / cols, (height - (rows - 1) * gap) / rows / 1.45, 104)
        if best is None or w > best["w"] + 1e-9:
            best = {"cols": cols, "rows": rows, "gap": gap, "w": w}
    best["h"] = best["w"] * 1.45
    return best


def short_pct(p: float) -> str:
    """0.2 -> "20%", 1/3 -> "33.3%"."""
    t = pct_text(decimal.Decimal(repr(p)) * 100, 1)
    return t.replace(".0%", "%")


def curve_lengths(o: tuple, c: tuple, i: tuple, steps: int = 24) -> list:
    """Distance along a quadratic curve at each of steps + 1 even parameter values, so a trail's tip stays on the ball."""
    pts = [((1 - u) ** 2 * o[0] + 2 * (1 - u) * u * c[0] + u * u * i[0],
            (1 - u) ** 2 * o[1] + 2 * (1 - u) * u * c[1] + u * u * i[1]) for u in (k / steps for k in range(steps + 1))]
    out = [0.0]
    for a, b in zip(pts, pts[1:]):
        out.append(out[-1] + math.dist(a, b))
    return [round(v, 1) for v in out]


def shot_plan(sc: dict) -> dict:
    """Where each of the toy shots lands. Exactly probability × trials go in, spread evenly through the run (never
    all at the end), at fixed positions: no randomness, so every render is the same."""
    n = sc["trials"]
    k = round(sc["probability"] * n)
    gx, gy, gw, gh = GOAL_BOX
    shots, gj, mj = [], 0, 0
    for i in range(n):
        goal = math.floor((i + 1) * k / n + 0.5) > math.floor(i * k / n + 0.5)
        if goal:
            u, v = (0.31 + 0.618034 * gj) % 1, (0.57 + 0.414214 * gj) % 1
            gj += 1
            ix, iy = gx + 50 + u * (gw - 100), gy + 36 + v * (gh - 72)
        else:
            u, side = (0.17 + 0.618034 * mj) % 1, mj % 3
            mj += 1
            if side == 0:
                ix, iy = gx - 40 - u * 50, gy + 40 + (1 - u) * 140   # wide of the left post
            elif side == 1:
                ix, iy = gx + 70 + u * (gw - 140), gy - 34 - u * 18   # over the bar
            else:
                ix, iy = gx + gw + 40 + u * 50, gy + 40 + u * 140      # wide of the right post
        c = ((SHOT_FROM[0] + ix) / 2 + (ix - SHOT_FROM[0]) * 0.1, iy - 70)
        shots.append({"goal": goal, "ix": round(ix, 1), "iy": round(iy, 1), "cx": round(c[0], 1), "cy": round(c[1], 1),
                      "cl": curve_lengths(SHOT_FROM, c, (ix, iy))})
    return {"n": n, "k": k, "p": sc["probability"], "from": list(SHOT_FROM), "pText": short_pct(sc["probability"]),
            "qText": short_pct(1 - sc["probability"]) if k < n else "0%", "list": shots}


def pitch_geometry(sc: dict, viewbox: tuple | None = None, lead: float = 0.5) -> dict:
    """Everything the pitch drawing and its animation need, in metres in the drawing."""
    view = sc.get("pitch_view", "half")
    pts = [pitch_point(view, float(x), float(y)) for x, y in sc["ball_path"]]
    lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    x, y = sc["ball_path"][-1]
    in_goal = x >= (0.995 if view == "full" else 0.99) and abs(y * PITCH_W - 34) <= GOAL_HALF
    players = []
    for pl in sc.get("players", []):
        px, py = pitch_point(view, float(pl["x"]), float(pl["y"]))
        players.append({"side": pl["side"], "x": round(px, 3), "y": round(py, 3)})
    return {"view": view, "pts": [[round(a, 3), round(b, 3)] for a, b in pts], "lens": [round(v, 3) for v in lens],
            "cum": [round(sum(lens[:i]), 3) for i in range(len(lens))], "total": round(sum(lens), 3),
            "players": players, "goal": [PITCH_L, 34.0] if view == "full" else [34.0, 0.0], "inGoal": in_goal,
            "vb": list(viewbox or PITCH_VIEWBOX[view]), "focus": sc.get("focus", "ball"), "lead": lead}


def pitch_lines() -> str:
    """The markings of a 105 x 68 m pitch, length along x and width along y."""
    c, L, dy = 34, PITCH_L, math.sqrt(9.15 ** 2 - 5.5 ** 2)

    def r(x, y, w, h):
        return f'<rect x="{x:g}" y="{y:.2f}" width="{w:g}" height="{h:.2f}"/>'
    return "".join([
        r(0, 0, L, PITCH_W), f'<line x1="52.5" y1="0" x2="52.5" y2="{PITCH_W:g}"/>', '<circle cx="52.5" cy="34" r="9.15"/>',
        r(0, c - 20.16, 16.5, 40.32), r(L - 16.5, c - 20.16, 16.5, 40.32), r(0, c - 9.16, 5.5, 18.32),
        r(L - 5.5, c - 9.16, 5.5, 18.32), r(-2, c - GOAL_HALF, 2, 2 * GOAL_HALF), r(L, c - GOAL_HALF, 2, 2 * GOAL_HALF),
        f'<path d="M16.5 {c - dy:.2f}A9.15 9.15 0 0 1 16.5 {c + dy:.2f}"/>',
        f'<path d="M{L - 16.5:g} {c - dy:.2f}A9.15 9.15 0 0 0 {L - 16.5:g} {c + dy:.2f}"/>',
        '<path d="M1 0A1 1 0 0 1 0 1"/>', f'<path d="M{L - 1:g} 0A1 1 0 0 0 {L:g} 1"/>',
        f'<path d="M0 {PITCH_W - 1:g}A1 1 0 0 1 1 {PITCH_W:g}"/>', f'<path d="M{L:g} {PITCH_W - 1:g}A1 1 0 0 0 {L - 1:g} {PITCH_W:g}"/>',
    ])


def pitch_svg(geo: dict) -> str:
    """A dark xEdge pitch (not grass) with the players, the ball and its trail. The camera moves the "cam" group."""
    turn = "" if geo["view"] == "full" else ' transform="matrix(0,-1,1,0,0,105)"'  # half: goal at the top
    stripes = "".join(f'<rect class="s{k % 2}" x="{k * 5.25:g}" y="0" width="5.25" height="{PITCH_W:g}"/>' for k in range(20))
    spots = "".join(f'<circle class="spot" cx="{x:g}" cy="34" r="0.32"/>' for x in (52.5, 11, 94))
    net = f'<rect class="netfx" x="{PITCH_L:g}" y="{34 - GOAL_HALF:.2f}" width="2" height="{2 * GOAL_HALF:.2f}"/>'
    d = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in geo["pts"])
    players = "".join(f'<circle class="{p["side"]}" cx="{p["x"]:.2f}" cy="{p["y"]:.2f}" r="1.25"/>' for p in geo["players"])
    x0, y0 = geo["pts"][0]
    vb = " ".join(f"{v:g}" for v in geo["vb"])
    return (f'<svg class="fx-pitch" viewBox="{vb}" preserveAspectRatio="xMidYMax meet"><g class="cam">'
            f'<g{turn}><g class="surf">{stripes}</g><g class="pl-lines">{pitch_lines()}</g>{spots}{net}</g>'
            f'<path class="trail" d="{d}" stroke-dasharray="{geo["total"]:.3f} 9999" stroke-dashoffset="{geo["total"]:.3f}"/>'
            f'<g class="pls">{players}</g><circle class="halo" cx="{x0:.2f}" cy="{y0:.2f}" r="2.6"/>'
            f'<circle class="ball" cx="{x0:.2f}" cy="{y0:.2f}" r="0.85"/></g></svg>')


def goal_face(gx: float, gy: float, gw: float) -> str:
    """A goal seen from the front, gw pixels wide (7.32 m), its top-left inside corner at gx, gy, with a faint net."""
    gh, post, step = gw * 2.44 / 7.32, gw * 0.12 / 7.32, gw / 14.64
    net = "".join(f'<line x1="{gx + k * step:.1f}" y1="{gy:.1f}" x2="{gx + k * step:.1f}" y2="{gy + gh:.1f}"/>' for k in range(1, 15))
    net += "".join(f'<line x1="{gx:.1f}" y1="{gy + k * step:.1f}" x2="{gx + gw:.1f}" y2="{gy + k * step:.1f}"/>'
                   for k in range(1, int(gh / step) + 1))
    return (f'<g class="net">{net}</g><rect class="netfx" x="{gx:.1f}" y="{gy:.1f}" width="{gw:.1f}" height="{gh:.1f}"/>'
            f'<rect class="post" x="{gx - post:.1f}" y="{gy - post:.1f}" width="{post:.1f}" height="{gh + post:.1f}"/>'
            f'<rect class="post" x="{gx + gw:.1f}" y="{gy - post:.1f}" width="{post:.1f}" height="{gh + post:.1f}"/>'
            f'<rect class="post" x="{gx - post:.1f}" y="{gy - post:.1f}" width="{gw + 2 * post:.1f}" height="{post:.1f}"/>')


def turf(top: float, bottom: float, width: float = 880, bands: int = 7) -> str:
    """Mowing stripes in front of a goal, closer together towards the goal, for depth."""
    ys = [top + (bottom - top) * (k / bands) ** 1.5 for k in range(bands + 1)]
    return "".join(f'<rect class="s{k % 2}" x="0" y="{a:.1f}" width="{width:g}" height="{b - a:.1f}"/>'
                   for k, (a, b) in enumerate(zip(ys, ys[1:])))


def shots_svg(plan: dict) -> str:
    gx, gy, gw, gh = GOAL_BOX
    ox, oy = SHOT_FROM
    shots = ""
    for s in plan["list"]:
        length = s["cl"][-1]
        shots += (f'<g class="shot {"g" if s["goal"] else "m"}"><path class="tr" d="M{ox:g} {oy:g}Q{s["cx"]:g} {s["cy"]:g} '
                  f'{s["ix"]:g} {s["iy"]:g}" stroke-dasharray="{length:.1f} 9999" stroke-dashoffset="{length:.1f}"/>'
                  f'<circle class="mk" cx="{s["ix"]:g}" cy="{s["iy"]:g}" r="11"/>'
                  f'<circle class="sb" cx="{ox:g}" cy="{oy:g}" r="24"/></g>')
    return (f'<svg class="fx-goalsvg" viewBox="0 0 880 440" preserveAspectRatio="xMidYMax meet">'
            f'<g class="turf">{turf(gy + gh, 440)}</g><line class="ground" x1="0" y1="{gy + gh:g}" x2="880" y2="{gy + gh:g}"/>'
            f'{goal_face(gx, gy, gw)}<circle class="spot" cx="{ox:g}" cy="{oy + 24:g}" r="5"/><g class="shots">{shots}</g></svg>')


HOOK_GOAL = {"gx": 200.0, "gy": 52.0, "gw": 480.0, "from": (262.0, 352.0), "to": (628.0, 96.0), "ctrl": (300.0, 70.0)}


def hook_goal_svg() -> str:
    g = HOOK_GOAL
    (ox, oy), (cx, cy), (ix, iy) = g["from"], g["ctrl"], g["to"]
    length = curve_lengths(g["from"], g["ctrl"], g["to"])[-1]
    bottom = g["gy"] + g["gw"] * 2.44 / 7.32
    return (f'<svg class="fx-goalsvg" viewBox="0 0 880 380" preserveAspectRatio="xMidYMax meet">'
            f'<g class="turf">{turf(bottom, 380)}</g><line class="ground" x1="0" y1="{bottom:.1f}" x2="880" y2="{bottom:.1f}"/>'
            f'{goal_face(g["gx"], g["gy"], g["gw"])}<g class="shot g"><path class="tr" d="M{ox:g} {oy:g}Q{cx:g} {cy:g} {ix:g} {iy:g}"'
            f' stroke-dasharray="{length:.1f} 9999" stroke-dashoffset="{length:.1f}"/><circle class="sb" cx="{ox:g}" cy="{oy:g}" r="28"/></g></svg>')


# ---------------------------------------------------------------- voice

class VoiceError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


API = "https://api.elevenlabs.io/v1"


def eleven(path: str, body: bytes, content_type: str, want_json: bool = True):
    """POST to the ElevenLabs API. The cloud environment's API credential adds the key."""
    req = urllib.request.Request(API + path, data=body, method="POST",
                                 headers={"Content-Type": content_type,
                                          "Accept": "application/json" if want_json else "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code in (401, 403):
            raise VoiceError(f"ElevenLabs refused the request ({e.code}): {detail}\nCheck the ElevenLabs API credential "
                             "on the cloud environment (host api.elevenlabs.io, header xi-api-key) and that the key "
                             "allows Text to Speech and Forced Alignment and has credits left.", e.code)
        raise VoiceError(f"ElevenLabs error {e.code} on {path.split('?')[0]}: {detail}", e.code)
    except (urllib.error.URLError, TimeoutError) as e:
        raise VoiceError(f"Couldn't reach api.elevenlabs.io ({e}). This needs a cloud environment with the ElevenLabs API credential.")
    return json.loads(raw) if want_json else raw


def forced_alignment(audio: bytes, text: str) -> dict:
    """Ask ElevenLabs when each character of the script is spoken in the audio."""
    boundary = "xedge" + hashlib.sha1(audio[:4096] + text.encode()).hexdigest()[:20]
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voice.mp3\"\r\n"
            f"Content-Type: audio/mpeg\r\n\r\n").encode() + audio + (
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\n{text}\r\n"
            f"--{boundary}--\r\n").encode()
    data = eleven("/forced-alignment", body, f"multipart/form-data; boundary={boundary}")
    chars = data.get("characters") or []
    return {"chars": [c.get("text", "") for c in chars], "starts": [float(c.get("start", 0)) for c in chars],
            "ends": [float(c.get("end", 0)) for c in chars]}


def map_alignment(text: str, align: dict) -> tuple:
    """Start and end time for every character of the script, filling any gaps by interpolation."""
    chars, st, en = align["chars"], align["starts"], align["ends"]
    s_out, e_out = [None] * len(text), [None] * len(text)
    j = 0
    for i, ch in enumerate(text):
        for k in range(j, min(len(chars), j + 12)):
            if chars[k].lower() == ch.lower():
                s_out[i], e_out[i] = float(st[k]), float(en[k])
                j = k + 1
                break
    known = [i for i, v in enumerate(s_out) if v is not None]
    if len(known) < 0.6 * len(text.replace(" ", "")):
        raise VoiceError("The voice timings don't match the script; try again or check the script for odd characters")
    for i in range(len(text)):
        if s_out[i] is None:
            prev = next((k for k in range(i - 1, -1, -1) if s_out[k] is not None and k in known), None)
            nxt = next((k for k in range(i + 1, len(text)) if k in known), None)
            if prev is None:
                s_out[i] = e_out[i] = s_out[nxt]
            elif nxt is None:
                s_out[i] = e_out[i] = e_out[prev]
            else:
                v = e_out[prev] + (i - prev) / (nxt - prev) * (s_out[nxt] - e_out[prev])
                s_out[i] = e_out[i] = v
    return s_out, e_out


def narrate(text: str, voice: dict, cache: pathlib.Path) -> tuple:
    """One continuous take of the whole script: (mp3 path, character starts, character ends, characters billed).
    Cached by everything that shapes the audio, so a re-render costs no credits."""
    model = voice["model_id"]
    settings = {"stability": voice["stability"], "similarity_boost": voice["similarity_boost"]}
    if model in V2_MODELS:
        settings.update({"style": voice["style"], "use_speaker_boost": True, "speed": voice["speed"]})
    body = {"text": text, "model_id": model, "voice_settings": settings}
    key = hashlib.sha1(json.dumps([voice["voice_id"], body], sort_keys=True).encode()).hexdigest()[:16]
    mp3, meta = cache / f"{key}.mp3", cache / f"{key}.json"
    if mp3.exists() and meta.exists():
        m = json.loads(meta.read_text())
        return mp3, m["starts"], m["ends"], 0
    vid = voice["voice_id"]
    align = None
    try:
        data = eleven(f"/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                      json.dumps(body).encode(), "application/json")
        audio = base64.b64decode(data["audio_base64"])
        a = data.get("alignment") or data.get("normalized_alignment")
        if a and a.get("characters"):
            align = {"chars": a["characters"], "starts": a["character_start_times_seconds"],
                     "ends": a["character_end_times_seconds"]}
    except VoiceError as e:
        if e.code not in (400, 404, 405, 422):
            raise
        audio = eleven(f"/text-to-speech/{vid}?output_format=mp3_44100_128", json.dumps(body).encode(),
                       "application/json", want_json=False)
    if align is None or "".join(align["chars"]) != text:
        align = forced_alignment(audio, text)
    starts, ends = map_alignment(text, align)
    cache.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(audio)
    meta.write_text(json.dumps({"starts": starts, "ends": ends, "model": model, "voice": vid}))
    return mp3, starts, ends, len(text)


def decode(mp3: pathlib.Path, out: pathlib.Path, tempo: float = 1.0) -> float:
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(mp3)]
    if tempo != 1.0:
        cmd += ["-filter:a", f"atempo={tempo}"]
    subprocess.run(cmd + ["-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(out)], check=True)
    with wave.open(str(out)) as w:
        return w.getnframes() / SR


def guess_times(spoken: str) -> tuple:
    rate = 14.0  # characters a second, about Chris's pace on Eleven v4
    starts, t = [], 0.0
    for ch in spoken:
        starts.append(t)
        t += 1 / rate + (0.25 if ch in ".?!" else 0.0)
    return starts, [s + 1 / rate for s in starts], t + 0.15


# ---------------------------------------------------------------- page

def rich_words(text: str) -> str:
    """Words as animatable spans; [[words]] in the brand colour."""
    groups, hl, after_space = [], False, True
    for part in re.split(r"(\[\[|\]\])", text):
        if part == "[[":
            hl = True
        elif part == "]]":
            hl = False
        elif part:
            for k, w in enumerate(part.split()):
                span = f'<span class="w{" hl" if hl else ""}">{html.escape(w)}</span>'
                # Punctuation straight after ]] (as in "[[still there]]?") stays with the word before it:
                # both go in one no-wrap group, so it can't drop onto a line of its own.
                if k == 0 and groups and not part[0].isspace() and not after_space:
                    groups[-1].append(span)
                else:
                    groups.append([span])
            after_space = part[-1].isspace()
    return " ".join(g[0] if len(g) == 1 else '<span style="white-space:nowrap">' + "".join(g) + "</span>"
                    for g in groups)


def num_parts(text: str):
    m = re.fullmatch(r"([^\d]*)(\d+(?:\.(\d+))?)([^\d]*)", str(text))
    if not m:
        return None
    return {"pre": m.group(1), "num": float(m.group(2)), "dec": len(m.group(3) or ""), "suf": m.group(4)}


def scene_html(i: int, sc: dict) -> str:
    e = html.escape
    kind = sc["type"]
    kicker = f'<div class="kicker">{e(sc["kicker"].upper())}</div>' if sc.get("kicker") else ""
    if kind == "hook":
        inner = f'{kicker}<h1 class="fit" data-min="64">{rich_words(sc["title"])}</h1>'
        if sc.get("visual") == "pitch":
            geo = pitch_geometry(HOOK_PITCH, HOOK_PITCH_VIEWBOX)
            inner += f'<div class="hvis" data-v="pitch"><div class="fx-tilt hook">{pitch_svg(geo)}</div></div>'
        elif sc.get("visual") == "goal":
            inner += f'<div class="hvis" data-v="goal">{hook_goal_svg()}</div>'
    elif kind == "pitch_story":
        geo = pitch_geometry(sc)
        inner = (f'{kicker}<h2 class="fx-title fit" data-min="44">{rich_words(sc["title"])}</h2>'
                 f'<div class="fx-stage"><div class="fx-tilt {geo["view"]}">{pitch_svg(geo)}</div>'
                 '<div class="fx-tag"><span class="dot"></span>ILLUSTRATION</div></div>')
    elif kind == "match_compare":
        c = compare_numbers(sc)
        ring = 2 * math.pi * 100
        offers = "".join(
            f'<div class="fx-offer"><div class="lab">{e(o["label"].upper())}</div>'
            f'<div class="fx-odds"><span class="v wfit" data-min="40">{o["odds"]}</span></div>'
            f'<div class="ringwrap"><svg viewBox="0 0 240 240"><circle class="trk" cx="120" cy="120" r="100"/>'
            f'<circle class="arc" cx="120" cy="120" r="100" stroke-dasharray="{ring:.3f} 9999" stroke-dashoffset="{ring:.3f}"'
            f' transform="rotate(-90 120 120)"/></svg><div class="pct"></div><div class="rcap">RAW IMPLIED</div></div></div>'
            for o in c["offers"])
        real = sc.get("source_status") == "real"
        label = sc.get("match_label") or "Example match"
        prov = ((f'SOURCE: {e(sc["source"].upper())} · {e(sc["date"])}' if real else "EXAMPLE PRICES") +
                "<br>RAW IMPLIED = 100 ÷ ODDS · THE MARGIN IS STILL IN")
        inner = (f'{kicker}<h2 class="fx-title fit" data-min="40">{rich_words(sc["title"])}</h2>'
                 f'<div class="fx-strip">{MINI_PITCH}<span class="ml">{e(label.upper())}</span>'
                 f'<span class="oc">{e(sc["outcome"].upper())}</span></div><div class="fx-offers"><svg class="bgp" viewBox="0 0 1040 420" preserveAspectRatio="none"><line x1="0" y1="210" x2="1040" y2="210"/><circle cx="520" cy="210" r="150"/><circle cx="520" cy="210" r="6"/><rect x="-200" y="40" width="1440" height="340"/></svg>{offers}</div>'
                 f'<div class="fx-gap"><span class="br"></span><span class="gl">{c["gap"]["text"]} PERCENTAGE POINTS</span></div>'
                 f'<div class="fx-prov">{prov}</div>')
    elif kind == "probability_pitch":
        plan = shot_plan(sc)
        inner = (f'{kicker}<h2 class="fx-title fit" data-min="44">{rich_words(sc["title"])}</h2>'
                 f'<div class="fx-stage pp">{shots_svg(plan)}<div class="fx-tag"><span class="dot"></span>'
                 f'TOY EXAMPLE · {plan["pText"]} CHANCE PER SHOT · NOT REAL DATA</div></div>'
                 '<div class="fx-count"><b class="g">0</b> <span class="gw">GOALS</span> FROM <b class="s">0</b> <span class="sw">SHOTS</span></div>'
                 '<div class="fx-split"><div class="a"></div><div class="b"></div></div>'
                 f'<div class="fx-splitlab"><span class="la">{plan["pText"]} GOAL</span><span class="lb">{plan["qText"]} NO GOAL</span></div>')
    elif kind == "football_stat":
        s, g = stat_numbers(sc), stat_grid(sc["denominator"])
        cells = '<span class="fx-m"></span>' * s["den"]
        if sc.get("source_status") == "real":
            prov = (f'SOURCE: {e(sc["source"].upper())} · {e(sc["date"])}<br>{e(sc["competition"].upper())} · '
                    f'{e(sc["window"].upper())}<br>{e(sc["definition"].upper())}')
        else:
            prov = "EXAMPLE · NOT REAL DATA"
        inner = (f'{kicker}<h2 class="fx-title fit" data-min="44">{rich_words(sc["title"])}</h2>'
                 f'<div class="fx-big wfit" data-min="110">{e(s["text"])}</div>'
                 f'<div class="fx-of">{s["num"]} OF {s["den"]} {e(sc["of_what"].upper())}</div>'
                 f'<div class="fx-grid" style="grid-template-columns:repeat({g["cols"]},{g["w"]:.1f}px);gap:{g["gap"]}px;'
                 f'--mh:{g["h"]:.1f}px">{cells}</div><div class="fx-prov">{prov}</div>')
    elif kind == "text":
        body = f'<p class="body fit" data-min="30">{e(sc["body"])}</p>' if sc.get("body") else ""
        inner = f'{kicker}<h1 class="fit t2" data-min="54">{rich_words(sc["title"])}</h1>{body}'
    elif kind == "prices":
        k2 = f'<div class="kicker k2">{e(sc["to_kicker"].upper())}</div>' if sc.get("to_kicker") else ""
        tiles = []
        for t in sc["tiles"]:
            sub = f'<span class="s1">{e(t.get("sub", ""))}</span>' + (f'<span class="s2">{e(t.get("to_sub", ""))}</span>' if t.get("to") else "")
            vals = f'<span class="v v1 wfit" data-min="40">{e(t["value"])}</span>' + (f'<span class="v v2 wfit" data-min="40">{e(t["to"])}</span>' if t.get("to") else "")
            tiles.append(f'<div class="tile"><div class="lab">{e(t["label"].upper())}</div><div class="vals">{vals}</div><div class="sub">{sub}</div></div>')
        inner = f'<div class="kwrap">{kicker}{k2}</div><div class="tiles">{"".join(tiles)}</div>'
    elif kind == "sum":
        terms = ' <span class="op">+</span> '.join(f'<span class="term">{e(str(v))}</span>' for v in sc["values"])
        bar = ""
        if str(sc["total"]).endswith("%"):
            bar = ('<div class="bar"><div class="f1"></div><div class="f2"></div><div class="mark"></div>'
                   '<div class="mlab">100% · A FAIR BOOK</div><div class="olab"></div></div>')
        inner = f'{kicker}<div class="eq wfit" data-min="30">{terms}</div><div class="total">{e(str(sc["total"]))}</div>{bar}'
    elif kind == "number":
        body = f'<p class="nbody fit" data-min="30">{e(sc["body"])}</p>' if sc.get("body") else ""
        inner = f'{kicker}<div class="big wfit" data-min="120">{e(sc["number"])}</div><h2 class="ntitle fit" data-min="44">{rich_words(sc["title"])}</h2>{body}'
    elif kind == "compare":
        title = f'<h2 class="ctitle fit" data-min="44">{rich_words(sc["title"])}</h2>' if sc.get("title") else ""
        rows = "".join(f'<div class="row{" hi" if b.get("hi") else ""}"><div class="rl"><span>{e(b["label"])}</span><b>{e(b["value"])}</b></div>'
                       f'<div class="track"><div class="fill"></div></div></div>' for b in sc["bars"])
        inner = f'{kicker}{title}<div class="rows">{rows}</div>'
    elif kind == "list":
        items = "".join(f'<li><span>{n:02d}</span><div>{e(str(t))}</div></li>' for n, t in enumerate(sc["items"], 1))
        inner = f'{kicker}<h2 class="ltitle fit" data-min="44">{rich_words(sc["title"])}</h2><ol>{items}</ol>'
    elif kind == "checker":
        c = sc["_checker"]
        ins = "".join(f'<div class="in"><div class="l">{lab}</div><div class="box"><span class="txt"></span><span class="caret"></span></div></div>'
                      for lab in ("HOME", "DRAW", "AWAY"))
        fair = "".join(f'<span class="fc"><span class="k">FAIR {lab}</span><span class="v">{c["fair"][j]}</span><span class="p">{c["prob"][j]}</span></span>'
                       for j, lab in enumerate(("HOME", "DRAW", "AWAY")))
        inner = ('<div class="chk"><div class="urlchip"><span class="dot"></span>xedge.live</div>'
                 '<div class="clab">FREE TOOL · MARGIN CHECKER</div><h2>How much margin is built into the odds?</h2>'
                 f'<div class="ins">{ins}</div><div class="res"><div class="hd"><span>Bookmaker margin</span><span class="m">{c["margin"]}</span></div>'
                 f'<div class="fair">{fair}</div><p class="note">Fair odds are the market’s odds with the bookmaker’s margin removed.</p></div></div>')
    elif kind == "end":
        body = f'<p class="ebody">{e(sc["body"])}</p>' if sc.get("body") else ""
        inner = (f'<img class="elogo" src="brand/xedge-logo-on-dark.svg" alt="xEdge"><h1 class="fit" data-min="56">{rich_words(sc["title"])}</h1>{body}'
                 '<div class="url">xedge.live</div><div class="esub">FREE MARGIN CHECKER · WAITLIST · UK ONLY</div>'
                 '<div class="ehelp">18+</div>')
    if kind == "hook" and sc.get("visual"):
        kind += " vis"
    return f'<section class="scene {kind}" id="s{i}">{inner}</section>'


CSS = """
@font-face{font-family:'Archivo';src:url('fonts/archivo-variable.woff2') format('woff2-variations');font-weight:100 900;font-stretch:62% 125%}
@font-face{font-family:'Geist Mono';src:url('fonts/geist-mono-400.woff2') format('woff2');font-weight:400}
@font-face{font-family:'Geist Mono';src:url('fonts/geist-mono-500.woff2') format('woff2');font-weight:500}
:root{--pitch:#0C0E0D;--volt:#C8F53A;--chalk:#F3F5EF;--stone:#A3A8A1;--label:#8A8F88;--faint:#6B7069;--surface:#141716;--line:#242927;--input:#2E3330;--grid:#171B19;--pill:#343936;--divider:#232826}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;background:var(--pitch);overflow:hidden}
body{font-family:'Archivo',sans-serif;color:var(--chalk);-webkit-font-smoothing:antialiased;position:relative}
#bg{position:absolute;left:0;right:0;top:-240px;height:2400px;background-image:linear-gradient(var(--grid) 2px,transparent 2px),linear-gradient(90deg,var(--grid) 2px,transparent 2px);background-size:120px 120px;background-position:-2px -2px}
#vig{position:absolute;inset:0;background:radial-gradient(ellipse 85% 60% at 50% 42%,rgba(12,14,13,0) 35%,rgba(12,14,13,.92) 100%)}
#head{position:absolute;left:80px;right:120px;top:196px;height:52px;display:flex;justify-content:space-between;align-items:center}
#head img{height:46px;display:block}
.pill{font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.08em;color:var(--stone);border:2px solid var(--pill);border-radius:999px;padding:8px 18px 7px}
.scene{position:absolute;left:80px;width:880px;top:350px;height:820px;display:flex;flex-direction:column;justify-content:center;opacity:0;overflow:hidden}
.kicker{font-family:'Geist Mono';font-weight:500;font-size:28px;letter-spacing:.1em;color:var(--label);margin-bottom:36px;white-space:nowrap}
h1{font-weight:800;font-stretch:125%;line-height:1.02;letter-spacing:-.012em;font-size:112px}
h1.t2{font-size:90px}
.hl{color:var(--volt)}
.w{display:inline-block}
.body{font-size:46px;line-height:1.32;color:var(--stone);margin-top:36px}
.kwrap{position:relative;height:70px}
.kwrap .kicker{position:absolute;left:0;top:0}
.tiles{display:flex;gap:26px}
.tile{flex:1;min-width:0;height:390px;background:var(--surface);border:2px solid var(--line);border-radius:30px;padding:30px 26px 28px;display:flex;flex-direction:column;justify-content:space-between}
.tile .lab{font-family:'Geist Mono';font-weight:500;font-size:26px;letter-spacing:.1em;color:var(--label)}
.tile .vals{position:relative;height:110px;overflow:visible}
.tile .v{position:absolute;left:0;bottom:0;font-weight:800;font-stretch:100%;font-size:92px;line-height:1;white-space:nowrap}
.tile .sub{position:relative;height:38px;font-family:'Geist Mono';font-weight:500;font-size:30px;color:var(--stone)}
.tile .sub span{position:absolute;left:0;top:0;white-space:nowrap}
.eq{font-family:'Geist Mono';font-weight:500;font-size:50px;white-space:nowrap;align-self:flex-start}
.eq .op{color:var(--label)}
.term{display:inline-block}
.total{font-weight:800;font-stretch:125%;font-size:176px;line-height:1;margin-top:30px;white-space:nowrap}
.bar{position:relative;margin-top:84px;height:40px;border-radius:20px;background:var(--surface);border:2px solid var(--line)}
.bar .f1{position:absolute;left:0;top:-2px;bottom:-2px;border-radius:20px 0 0 20px;background:var(--stone)}
.bar .f2{position:absolute;top:-2px;bottom:-2px;background:var(--volt);border-radius:0 20px 20px 0}
.bar .mark{position:absolute;top:-26px;bottom:-26px;width:4px;margin-left:-2px;background:var(--chalk)}
.bar .mlab{position:absolute;top:74px;font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.08em;color:var(--label);white-space:nowrap;transform:translateX(-100%)}
.bar .olab{position:absolute;top:-74px;font-family:'Geist Mono';font-weight:500;font-size:34px;color:var(--volt);white-space:nowrap;transform:translateX(-50%)}
.big{font-weight:800;font-stretch:112%;font-size:300px;line-height:.9;color:var(--volt);letter-spacing:-.03em;white-space:nowrap;align-self:flex-start;transform-origin:0 70%}
.ntitle{font-weight:800;font-stretch:125%;font-size:74px;line-height:1.05;margin-top:46px}
.nbody{font-size:46px;line-height:1.3;color:var(--stone);margin-top:26px}
.ctitle,.ltitle{font-weight:800;font-stretch:125%;font-size:72px;line-height:1.05}
.rows{margin-top:30px}
.row{margin-top:58px}
.rl{display:flex;justify-content:space-between;align-items:baseline;font-size:46px;font-weight:600}
.rl b{font-family:'Geist Mono';font-weight:500;font-size:52px}
.row.hi .rl b{color:var(--volt)}
.track{position:relative;height:60px;margin-top:18px;border-radius:30px;background:var(--surface);border:2px solid var(--line);overflow:hidden}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:30px;background:var(--stone)}
.row.hi .fill{background:var(--volt)}
ol{list-style:none;margin-top:40px;border-top:2px solid var(--divider)}
li{display:grid;grid-template-columns:84px 1fr;align-items:baseline;padding:28px 0;border-bottom:2px solid var(--divider)}
li span{font-family:'Geist Mono';font-weight:500;font-size:32px;color:var(--volt)}
li div{font-size:52px;line-height:1.22;font-weight:500}
.scene.checker{top:330px;height:860px}
.urlchip{align-self:flex-start;display:inline-flex;align-items:center;gap:14px;font-family:'Geist Mono';font-weight:500;font-size:26px;color:var(--stone);border:2px solid var(--pill);border-radius:999px;padding:10px 24px 9px;margin-bottom:30px}
.urlchip .dot{width:14px;height:14px;border-radius:50%;background:var(--volt)}
.chk{display:flex;flex-direction:column}
.clab{font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.08em;color:var(--volt)}
.chk h2{font-weight:800;font-stretch:125%;font-size:48px;line-height:1.1;margin-top:16px}
.ins{display:flex;gap:22px;margin-top:34px}
.in{flex:1}
.in .l{font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.08em;color:var(--label);margin-bottom:12px}
.box{height:100px;background:var(--surface);border:2px solid var(--input);border-radius:24px;padding:0 24px;display:flex;align-items:center;font-family:'Geist Mono';font-weight:500;font-size:42px}
.box.focus{border-color:var(--stone)}
.caret{display:inline-block;width:3px;height:46px;background:var(--chalk);margin-left:3px;opacity:0}
.res{margin-top:26px;background:var(--surface);border:2px solid var(--line);border-radius:36px;padding:34px 36px}
.hd{display:flex;justify-content:space-between;align-items:center;font-size:34px}
.hd .m{font-weight:800;font-stretch:125%;font-size:70px;color:var(--volt)}
.fair{display:flex;justify-content:space-between;margin-top:26px;padding-top:26px;border-top:2px solid var(--divider)}
.fc .k{display:block;font-family:'Geist Mono';font-size:21px;letter-spacing:.08em;color:var(--label)}
.fc .v{display:block;font-family:'Geist Mono';font-weight:500;font-size:44px;margin-top:8px}
.fc .p{display:block;font-size:26px;color:var(--label);margin-top:4px}
.res .note{font-size:24px;line-height:1.4;color:var(--label);margin-top:24px}
.scene.end{top:300px;height:1000px}
.elogo{height:86px;align-self:flex-start;transform-origin:0 50%}
.end h1{font-size:96px;margin-top:76px}
.ebody{font-size:44px;line-height:1.3;color:var(--stone);margin-top:28px}
.url{font-weight:800;font-stretch:125%;font-size:124px;line-height:1;color:var(--volt);margin-top:64px;white-space:nowrap}
.esub{font-family:'Geist Mono';font-weight:500;font-size:26px;letter-spacing:.08em;color:var(--label);margin-top:24px}
.ehelp{margin-top:64px;padding-top:36px;border-top:2px solid var(--divider);font-family:'Geist Mono';font-weight:500;font-size:30px;line-height:1.5;color:var(--stone)}
#cap{position:absolute;left:80px;width:880px;top:1200px;height:110px;display:flex;align-items:center;justify-content:center;text-align:center;font-weight:700;font-size:58px;line-height:1.1;opacity:0}
#cap .ln{display:inline}
#cap .cw{color:var(--faint)}
#cap .cw.on{color:var(--chalk)}
.scene.pitch_story,.scene.match_compare,.scene.probability_pitch,.scene.football_stat{justify-content:flex-start}
.fx-title{font-weight:800;font-stretch:125%;font-size:64px;line-height:1.04;letter-spacing:-.01em}
.fx-stage{position:relative;flex:1;min-height:0;margin-top:30px}
.fx-tilt{position:absolute;inset:0;perspective:1600px;perspective-origin:50% 0}
.fx-tilt svg{position:absolute;left:0;top:0;width:100%;height:100%;transform-origin:50% 100%;transform:rotateX(24deg)}
.fx-tilt.full svg{transform:rotateX(18deg)}
.fx-pitch .s0{fill:#121715}.fx-pitch .s1{fill:#0F1312}
.fx-pitch .pl-lines{fill:none;stroke:rgba(243,245,239,.44);stroke-width:.3}
.fx-pitch .spot{fill:rgba(243,245,239,.6)}
.fx-pitch .netfx,.fx-goalsvg .netfx{fill:var(--volt);opacity:0}
.fx-pitch .trail{fill:none;stroke:var(--volt);stroke-width:.6;stroke-linecap:round;stroke-linejoin:round}
.fx-pitch .home{fill:var(--chalk);stroke:var(--pitch);stroke-width:.35}
.fx-pitch .away{fill:var(--pitch);stroke:var(--stone);stroke-width:.55}
.fx-pitch .ball{fill:#fff}.fx-pitch .halo{fill:var(--volt);opacity:.24}
.fx-tag{position:absolute;left:0;top:0;display:flex;align-items:center;gap:12px;font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.1em;color:var(--stone);white-space:nowrap}
.fx-tag .dot{width:12px;height:12px;border-radius:50%;background:var(--volt);flex:none}
.fx-goalsvg{position:absolute;inset:0;width:100%;height:100%}
.fx-goalsvg .s0{fill:#111614}.fx-goalsvg .s1{fill:#0E1211}
.fx-goalsvg .ground{stroke:rgba(243,245,239,.38);stroke-width:3}
.fx-goalsvg .net line{stroke:rgba(243,245,239,.13);stroke-width:2}
.fx-goalsvg .post{fill:var(--chalk)}
.fx-goalsvg .spot{fill:rgba(243,245,239,.5)}
.fx-goalsvg .tr{fill:none;stroke-width:6;stroke-linecap:round}
.fx-goalsvg .shot.g .tr{stroke:var(--volt)}.fx-goalsvg .shot.m .tr{stroke:var(--stone)}
.fx-goalsvg .sb{fill:#fff}
.fx-goalsvg .shot.g .mk{fill:var(--volt)}.fx-goalsvg .shot.m .mk{fill:none;stroke:var(--stone);stroke-width:4}
.fx-stage.pp .fx-tag{top:auto;bottom:-46px}
.fx-count{margin-top:62px;font-family:'Geist Mono';font-weight:500;font-size:32px;letter-spacing:.06em;color:var(--stone)}
.fx-count b{font-weight:500;color:var(--chalk)}
.fx-split{position:relative;margin-top:22px;height:40px;border-radius:20px;background:var(--surface);border:2px solid var(--line);overflow:hidden}
.fx-split .a{position:absolute;left:0;top:0;bottom:0;background:var(--volt)}
.fx-split .b{position:absolute;right:0;top:0;bottom:0;background:var(--stone);opacity:.5}
.fx-splitlab{display:flex;justify-content:space-between;margin-top:14px;font-family:'Geist Mono';font-weight:500;font-size:28px;letter-spacing:.06em}
.fx-splitlab .la{color:var(--volt)}.fx-splitlab .lb{color:var(--stone)}
.fx-strip{display:flex;align-items:center;gap:18px;margin-top:26px;height:76px;padding:0 24px;flex:none;background:var(--surface);border:2px solid var(--line);border-radius:22px;font-family:'Geist Mono';font-weight:500;font-size:25px;letter-spacing:.08em}
.fx-strip .mini{width:60px;height:40px;flex:none;fill:none;stroke:rgba(243,245,239,.5);stroke-width:2}
.fx-strip .ml{color:var(--chalk);white-space:nowrap}
.fx-strip .oc{margin-left:auto;color:var(--volt);white-space:nowrap}
.fx-offers{position:relative;display:flex;gap:24px;margin-top:26px}
.fx-offers .bgp{position:absolute;left:-80px;right:-80px;top:-10px;height:420px;fill:none;stroke:rgba(243,245,239,.07);stroke-width:3}
.fx-offer{position:relative}
.fx-offer{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center}
.fx-offer .lab{font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.1em;color:var(--label);white-space:nowrap}
.fx-odds{position:relative;width:100%;height:88px;margin-top:6px;display:flex;justify-content:center}
.fx-odds .v{font-family:'Geist Mono';font-weight:500;font-size:80px;line-height:88px;white-space:nowrap}
.ringwrap{position:relative;width:244px;height:244px;margin-top:12px}
.ringwrap svg{position:absolute;inset:0;width:100%;height:100%}
.ringwrap .trk{fill:none;stroke:var(--surface);stroke-width:16}
.ringwrap .arc{fill:none;stroke:var(--chalk);stroke-width:16}
.ringwrap .pct{position:absolute;left:0;right:0;top:84px;text-align:center;font-weight:800;font-stretch:105%;font-size:44px;line-height:1}
.ringwrap .rcap{position:absolute;left:0;right:0;top:138px;text-align:center;font-family:'Geist Mono';font-weight:500;font-size:19px;letter-spacing:.08em;color:var(--label)}
.fx-gap{position:relative;height:84px;margin-top:16px;flex:none}
.fx-gap .br{position:absolute;top:0;width:0;height:24px;border:4px solid var(--volt);border-top:none;border-radius:0 0 10px 10px}
.fx-gap .gl{position:absolute;left:0;top:38px;font-family:'Geist Mono';font-weight:500;font-size:30px;letter-spacing:.04em;color:var(--volt);white-space:nowrap}
.fx-prov{margin-top:auto;font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.06em;line-height:1.5;color:var(--label)}
.fx-big{font-weight:800;font-stretch:112%;font-size:190px;line-height:.92;color:var(--volt);letter-spacing:-.03em;white-space:nowrap;align-self:flex-start;margin-top:22px}
.fx-of{font-family:'Geist Mono';font-weight:500;font-size:32px;letter-spacing:.07em;margin-top:18px}
.fx-grid{display:grid;margin-top:26px;flex:none}
.fx-m{position:relative;height:var(--mh);border:2px solid rgba(243,245,239,.3);border-radius:5px}
.fx-m::before{content:'';position:absolute;left:0;right:0;top:50%;border-top:2px solid rgba(243,245,239,.22)}
.fx-m::after{content:'';position:absolute;left:50%;top:50%;width:36%;aspect-ratio:1;border:2px solid rgba(243,245,239,.22);border-radius:50%;transform:translate(-50%,-50%)}
.fx-m.on{background:var(--volt);border-color:var(--volt)}
.fx-m.on::before,.fx-m.on::after{border-color:rgba(12,14,13,.4)}
.scene.hook.vis{justify-content:flex-start;padding-top:10px}
.hook.vis h1{font-size:96px}
.hvis{position:relative;flex:1;min-height:300px;margin-top:40px}
.hvis .fx-tilt svg{transform:rotateX(38deg)}
.hvis>.fx-goalsvg{transform-origin:50% 60%}
"""

JS = r"""
const D = __DATA__;
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
function bez(x1,y1,x2,y2){
  const cx=3*x1,bx=3*(x2-x1)-cx,ax=1-cx-bx,cy=3*y1,by=3*(y2-y1)-cy,ay=1-cy-by;
  const X=t=>((ax*t+bx)*t+cx)*t, Y=t=>((ay*t+by)*t+cy)*t, dX=t=>(3*ax*t+2*bx)*t+cx;
  return x=>{ if(x<=0) return 0; if(x>=1) return 1; let lo=0,hi=1,t=x;
    for(let i=0;i<10;i++){const err=X(t)-x,d=dX(t); if(Math.abs(err)<1e-7) break; if(Math.abs(d)<1e-6) break; t=clamp(t-err/d);}
    for(let i=0;i<40 && Math.abs(X(t)-x)>1e-6;i++){ if(X(t)<x) lo=t; else hi=t; t=(lo+hi)/2; }
    return Y(t); };
}
const EO=bez(.16,1,.3,1), ES=bez(.2,.9,.3,1);
const P=(t,a,d)=>clamp((t-a)/d);
const HELP_IN=0.38, HELP_RISE=0.35;  // the end card's 18+ line: starts rising this long after the card, over this long
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
function rise(el,k,dy=30){ if(!el) return; el.style.opacity=k; el.style.transform=`translateY(${(1-k)*dy}px)`; }
function fmt(n,k){ return n.pre+(n.num*k).toFixed(n.dec)+n.suf; }
function beat(sc,i,fallback){ const b=sc.beats[i]; return (b===undefined||b===null)?fallback:b; }
// ---- football scenes. Everything is worked out from t alone (no clocks, no randomness), so any frame can be
// rendered on its own and comes out the same every time.
function segPlan(g,beats,start0,end){
  // When each pass starts and how long it takes: {n} beats start passes; otherwise each follows the last.
  // The ball always arrives (and a goal shows) before the scene moves on: late passes are quicker.
  const n=g.lens.length, st=[], du=[]; let prev=start0;
  for(let i=0;i<n;i++){ const b=beats[i]; const s=(b===undefined||b===null)?prev:b; st.push(s); du.push(clamp(0.35+g.lens[i]/38,0.45,1.6)); prev=s+du[i]; }
  for(let i=0;i<n-1;i++){ if(st[i+1]<st[i]+du[i]) du[i]=Math.max(0.25,st[i+1]-st[i]); }
  if(end!==undefined){ const room=end-0.75-st[n-1]; if(du[n-1]>room) du[n-1]=Math.max(0.3,room); }
  return {st,du};
}
// A kicked ball slows at a steady rate, so it travels on a quadratic ease-out: it leaves the foot at twice its
// average speed and rolls to a stop, with no jump.
const KICK=x=>{ const v=1-clamp(x); return 1-v*v; };
function ballAt(g,pl,t){
  for(let i=g.lens.length-1;i>=0;i--){ if(t>=pl.st[i]){ const u=KICK((t-pl.st[i])/pl.du[i]), a=g.pts[i], b=g.pts[i+1];
    return [a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u, g.cum[i]+g.lens[i]*u]; } }
  return [g.pts[0][0], g.pts[0][1], 0];
}
function pitchFrame(g,root,t,beats,t0,t1){
  const pl=segPlan(g,beats,t0+g.lead,t1), b=ballAt(g,pl,t);
  for(const c of [$('.ball',root),$('.halo',root)]){ c.setAttribute('cx',b[0].toFixed(3)); c.setAttribute('cy',b[1].toFixed(3)); }
  $('.trail',root).style.strokeDashoffset=Math.max(0,g.total-b[2]).toFixed(3);
  // Camera on the pitch only (never the captions or the 18+): a slow push-in that follows the ball, or the goal.
  const dur=Math.max(1.5,t1-t0), vb=g.vb, mx=vb[0]+vb[2]/2, my=vb[1]+vb[3]/2;
  const zoom=u=>1+0.14*ES(P(u,t0,dur)), inside=(x,y,z)=>[clamp(x,vb[0]+vb[2]/(2*z),vb[0]+vb[2]-vb[2]/(2*z)),
                                                        clamp(y,vb[1]+vb[3]/(2*z),vb[1]+vb[3]-vb[3]/(2*z))];
  let s=1, cx=mx, cy=my;
  if(g.focus==='ball'){
    // The camera trails the ball by about a third of a second: the average of eight recent framings, each kept
    // inside the pitch, so it eases in and out of every move and never shows past the drawing's edge.
    s=zoom(t); cx=0; cy=0;
    for(let k=0;k<8;k++){ const u=t-k*0.1, q=ballAt(g,pl,u), c=inside(q[0],q[1],zoom(u)); cx+=c[0]/8; cy+=c[1]/8; }
  } else if(g.focus==='goal'){ const k=ES(P(t,t0,dur)); s=1+0.14*k; [cx,cy]=inside(mx+(g.goal[0]-mx)*k,my+(g.goal[1]-my)*k,s); }
  $('.cam',root).setAttribute('transform',`translate(${mx.toFixed(3)} ${my.toFixed(3)}) scale(${s.toFixed(5)}) translate(${(-cx).toFixed(3)} ${(-cy).toFixed(3)})`);
  $$('.pls circle',root).forEach((c,i)=>{ c.style.opacity=g.lead<0.2?1:EO(P(t,t0+0.08+i*0.025,0.3)).toFixed(4); });
  const nf=$('.netfx',root), last=g.lens.length-1, arr=pl.st[last]+pl.du[last];
  nf.style.opacity=g.inGoal?(0.18*P(t,arr-0.05,0.15)+0.5*Math.sin(Math.PI*P(t,arr-0.05,0.7))).toFixed(4):0;
}
function curveAt(o,c,i,u){ const v=1-u; return [v*v*o[0]+2*v*u*c[0]+u*u*i[0], v*v*o[1]+2*v*u*c[1]+u*u*i[1]]; }
function lenAt(cl,u){ const x=u*(cl.length-1), k=Math.min(cl.length-2,Math.floor(x)); return cl[k]+(cl[k+1]-cl[k])*(x-k); }
const HV={
  // The hook's football picture: in place from the first frame, already moving.
  pitch(sc,hv,t){ pitchFrame(sc.geo,hv,t,[],sc.t0,sc.t1); },  // its camera keeps pushing in after the pass
  goal(sc,hv,t){
    const x=P(t,sc.t0+0.03,1.7), h=sc.hv, u=0.93*(1-(1-x)*(1-x)), p=curveAt(h.from,h.ctrl,h.to,u), ball=$('.sb',hv);
    const z=1+0.05*ES(P(t,sc.t0,Math.max(1.5,sc.t1-sc.t0))); $('svg',hv).style.transform=`scale(${z.toFixed(5)})`;
    ball.setAttribute('cx',p[0].toFixed(2)); ball.setAttribute('cy',p[1].toFixed(2)); ball.setAttribute('r',(28-15*u).toFixed(2));
    $('.tr',hv).style.strokeDashoffset=(h.cl[h.cl.length-1]-lenAt(h.cl,u)).toFixed(2);
  },
};
const U = {
  hook(sc,el,t){
    // Fast entrance: words start at once and the whole title is in by about 0.6 s,
    // then a slow push-in keeps the hook moving until the next scene.
    rise($('.kicker',el),EO(P(t,sc.t0,0.35)),20);
    $$('.w',el).forEach((w,i)=>rise(w,EO(P(t,sc.t0+i*0.04,0.38)),56));
    const h=$('h1',el); if(h){ h.style.transformOrigin='left center'; h.style.transform=`scale(${1+0.035*ES(P(t,sc.t0,Math.max(0.5,sc.t1-sc.t0)))})`; }
    const hv=$('.hvis',el); if(hv) HV[hv.dataset.v](sc,hv,t);
  },
  pitch_story(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.45)),20);
    rise($('.fx-title',el),EO(P(t,sc.t0+0.05,0.5)),28);
    const st=$('.fx-stage',el), k=EO(P(t,sc.t0+0.08,0.6));
    st.style.opacity=k; st.style.transform=`translateY(${((1-k)*30).toFixed(2)}px)`;
    pitchFrame(sc.geo,el,t,sc.beats,sc.t0,sc.t1);
  },
  match_compare(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.45)),20);
    rise($('.fx-title',el),EO(P(t,sc.t0+0.05,0.5)),28);
    rise($('.fx-strip',el),EO(P(t,sc.t0+0.15,0.5)),20);
    const cols=$$('.fx-offer',el), n=cols.length; let last=sc.t0;
    cols.forEach((c,i)=>{ const tin=beat(sc,i,sc.t0+0.4+i*0.35); last=tin; const k=EO(P(t,tin-0.08,0.45));
      c.style.opacity=k; c.style.transform=`translateY(${((1-k)*44).toFixed(2)}px)`; });
    const tc=beat(sc,n,last+0.9), C=2*Math.PI*100;
    cols.forEach((c,i)=>{
      const o=sc.offers[i], g=ES(P(t,tc+i*0.15,1.0));
      $('.arc',c).style.strokeDashoffset=(C*(1-o.raw/100*g)).toFixed(3);
      const pct=$('.pct',c); pct.textContent=g>=1?o.rawText:(o.raw*g).toFixed(1)+'%';  // lands exactly on the worked-out figure
      pct.style.opacity=EO(P(t,tc-0.05,0.3)); $('.rcap',c).style.opacity=EO(P(t,tc+0.1,0.4));
    });
    const tg=beat(sc,n+1,tc+1.6), k=EO(P(t,tg,0.55));
    const a=cols[sc.gap.hi], b=cols[sc.gap.lo], xa=a.offsetLeft+a.offsetWidth/2, xb=b.offsetLeft+b.offsetWidth/2;
    const x0=Math.min(xa,xb), w=Math.abs(xa-xb), br=$('.fx-gap .br',el), gl=$('.fx-gap .gl',el);
    br.style.left=(x0+w*(1-k)/2).toFixed(2)+'px'; br.style.width=(w*k).toFixed(2)+'px'; br.style.opacity=k>0?1:0;
    gl.style.left=clamp(x0+w/2-gl.offsetWidth/2,0,el.clientWidth-gl.offsetWidth).toFixed(2)+'px'; rise(gl,EO(P(t,tg+0.2,0.45)),12);
    rise($('.fx-prov',el),EO(P(t,sc.t0+0.5,0.45)),10);
  },
  probability_pitch(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.45)),20);
    rise($('.fx-title',el),EO(P(t,sc.t0+0.05,0.5)),28);
    const st=$('.fx-stage',el); st.style.opacity=EO(P(t,sc.t0+0.08,0.55));
    const S=sc.shots, n=S.list.length, start=beat(sc,0,sc.t0+0.8), sum=beat(sc,1,null);
    const sp=clamp(((sum!==null?sum-0.3:sc.t1-1.4)-start-0.55)/n,0.2,0.5);
    let goals=0, landed=0;
    $$('.shot',el).forEach((g,i)=>{
      const s=S.list[i], ts=start+i*sp, u=P(t,ts,0.55), e=KICK(u), ball=$('.sb',g), tr=$('.tr',g), mk=$('.mk',g);
      const L=s.cl[s.cl.length-1], p=curveAt(S.from,[s.cx,s.cy],[s.ix,s.iy],e);
      ball.style.opacity=(t>=ts&&u<1)?1:0; ball.setAttribute('cx',p[0].toFixed(2)); ball.setAttribute('cy',p[1].toFixed(2)); ball.setAttribute('r',(24-13*e).toFixed(2));
      tr.style.strokeDashoffset=(L-lenAt(s.cl,e)).toFixed(2);
      tr.style.opacity=t<ts?0:(u<1?0.95:(0.95-(0.95-(s.goal?0.3:0.1))*EO(P(t,ts+0.55,0.6)))).toFixed(4);
      const m=EO(P(t,ts+0.5,0.25)); mk.style.opacity=m; mk.setAttribute('r',(11*(0.6+0.4*m)).toFixed(2));
      if(t>=ts+0.55){ landed++; if(s.goal) goals++; }
    });
    $('.fx-count .g',el).textContent=goals; $('.fx-count .s',el).textContent=landed;
    $('.fx-count .gw',el).textContent=goals===1?'GOAL':'GOALS'; $('.fx-count .sw',el).textContent=landed===1?'SHOT':'SHOTS';
    const tsum=sum!==null?sum:start+n*sp+0.8, ka=ES(P(t,tsum,0.8)), kb=ES(P(t,tsum+0.25,0.8));
    $('.fx-split .a',el).style.width=(S.p*100*ka).toFixed(3)+'%'; $('.fx-split .b',el).style.width=((1-S.p)*100*kb).toFixed(3)+'%';
    rise($('.fx-splitlab .la',el),EO(P(t,tsum+0.1,0.4)),12); rise($('.fx-splitlab .lb',el),EO(P(t,tsum+0.35,0.4)),12);
  },
  football_stat(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.45)),20);
    rise($('.fx-title',el),EO(P(t,sc.t0+0.05,0.5)),28);
    const big=$('.fx-big',el), s=sc.stat, k=EO(P(t,sc.t0+0.1,0.5)), g=ES(P(t,sc.t0+0.1,0.9));
    big.style.opacity=k; big.style.transform=`scale(${(0.9+0.1*k).toFixed(4)})`; big.style.transformOrigin='0 70%';
    big.textContent=g>=1?s.text:(s.pct*g).toFixed(s.dec)+'%';
    const t1=beat(sc,0,sc.t0+0.8), ms=$$('.fx-m',el), stag=Math.min(0.04,0.9/ms.length);
    ms.forEach((m,i)=>{ const a=EO(P(t,t1+i*stag,0.3)); m.style.opacity=a; m.style.transform=`translateY(${((1-a)*14).toFixed(2)}px)`; });
    const t2=beat(sc,1,t1+Math.max(0.9,ms.length*stag+0.4)), stag2=Math.min(0.08,0.9/Math.max(1,s.num));
    ms.forEach((m,i)=>m.classList.toggle('on',i<s.num && t>=t2+i*stag2));
    rise($('.fx-of',el),EO(P(t,t1,0.45)),16); rise($('.fx-prov',el),EO(P(t,t1+0.3,0.45)),10);
  },
  text(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    $$('h1 .w',el).forEach((w,i)=>rise(w,EO(P(t,sc.t0+0.06+i*0.05,0.5)),40));
    rise($('.body',el),EO(P(t,sc.t0+0.5,0.6)),24);
  },
  prices(sc,el,t){
    const tiles=$$('.tile',el), n=tiles.length, conv=tiles.length && !!$('.v2',tiles[0]);
    let firstConv=null;
    tiles.forEach((tile,i)=>{
      const tin=beat(sc,i,sc.t0+0.25+i*0.3);
      const k=EO(P(t,tin-0.08,0.5));
      tile.style.opacity=k; tile.style.transform=`translateY(${(1-k)*48}px) scale(${0.94+0.06*k})`;
      if(!conv) return;
      const tc=beat(sc,n+i,null);
      if(i===0) firstConv=tc;
      const c=tc===null?0:ES(P(t,tc-0.06,0.45));
      const v1=$('.v1',tile),v2=$('.v2',tile),s1=$('.s1',tile),s2=$('.s2',tile);
      v1.style.opacity=1-c; v1.style.transform=`translateY(${-c*70}px)`;
      v2.style.opacity=c; v2.style.transform=`translateY(${(1-c)*70}px)`;
      if(s1){s1.style.opacity=1-c;} if(s2){s2.style.opacity=c;}
      const glow=tc===null?0:Math.sin(Math.PI*P(t,tc-0.06,0.6));
      tile.style.borderColor=`rgba(200,245,58,${0.55*glow})`;
    });
    const k1=$('.kwrap .kicker:not(.k2)',el), k2=$('.k2',el);
    const out=(firstConv===null||!k2)?0:P(t,firstConv-0.42,0.18), inn=(firstConv===null||!k2)?0:EO(P(t,firstConv-0.2,0.35));
    rise(k1,EO(P(t,sc.t0,0.5))*(1-out),20); if(k2) rise(k2,inn,20);
  },
  sum(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    $$('.term,.op',el).forEach((x,i)=>rise(x,EO(P(t,sc.t0+0.12+i*0.09,0.45)),26));
    const tb=beat(sc,0,sc.t0+0.9);
    const tot=$('.total',el); const g=ES(P(t,tb-0.1,0.9));
    tot.style.opacity=EO(P(t,tb-0.12,0.3)); tot.textContent=fmt(sc.totalNum,g);
    const bar=$('.bar',el); if(!bar) return;
    rise(bar,EO(P(t,sc.t0+0.35,0.5)),24);
    const max=Math.max(100,sc.totalNum.num), Wd=bar.clientWidth;  // the bar ends at the total, or at 100% if the total is lower
    const cur=sc.totalNum.num*g;
    $('.f1',bar).style.width=(Math.min(cur,100)/max*Wd)+'px';
    const f2=$('.f2',bar); f2.style.left=(100/max*Wd)+'px'; f2.style.width=(Math.max(0,cur-100)/max*Wd)+'px';
    $('.mark',bar).style.left=(100/max*Wd)+'px';
    const ml=$('.mlab',bar); ml.style.left=(100/max*Wd+2)+'px'; ml.style.opacity=EO(P(t,beat(sc,1,tb+0.9)-0.1,0.4));
    const ol=$('.olab',bar);
    if(sc.totalNum.num>100){ ol.textContent='+'+(sc.totalNum.num-100).toFixed(sc.totalNum.dec)+'%';
      ol.style.left=Math.min((100+(sc.totalNum.num-100)/2)/max*Wd, Wd-ol.offsetWidth/2)+'px'; ol.style.opacity=EO(P(t,tb+0.75,0.35)); } else ol.style.opacity=0;
  },
  number(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    const big=$('.big',el), k=EO(P(t,sc.t0+0.04,0.55));
    big.style.opacity=k; big.style.transform=`scale(${0.86+0.14*k})`;
    if(sc.numParts) big.textContent=fmt(sc.numParts,ES(P(t,sc.t0+0.04,0.85)));
    rise($('.ntitle',el),EO(P(t,sc.t0+0.38,0.55)),30);
    rise($('.nbody',el),EO(P(t,sc.t0+0.62,0.55)),24);
  },
  compare(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    rise($('.ctitle',el),EO(P(t,sc.t0+0.1,0.5)),30);
    $$('.row',el).forEach((r,i)=>{
      const tb=beat(sc,i,sc.t0+0.45+i*0.7);
      rise(r,EO(P(t,tb-0.3,0.4)),24);
      const g=ES(P(t,tb-0.05,0.9)), v=sc.barVals[i];
      $('.fill',r).style.width=(v.num*g)+'%'; $('.rl b',r).textContent=fmt(v,g);
    });
  },
  list(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    rise($('.ltitle',el),EO(P(t,sc.t0+0.05,0.5)),30);
    $$('li',el).forEach((li,i)=>rise(li,EO(P(t,beat(sc,i,sc.t0+0.5+i*0.6)-0.1,0.5)),30));
  },
  checker(sc,el,t){
    rise($('.urlchip',el),EO(P(t,sc.t0,0.45)),20);
    rise($('.clab',el),EO(P(t,sc.t0+0.06,0.45)),20);
    rise($('h2',el),EO(P(t,sc.t0+0.12,0.5)),24);
    rise($('.ins',el),EO(P(t,sc.t0+0.2,0.5)),24);
    rise($('.res',el),EO(P(t,sc.t0+0.28,0.5)),24);
    let tt=beat(sc,0,sc.t0+0.45);
    const per=0.08;
    $$('.box',el).forEach((b,i)=>{
      const s=sc.odds[i], t0=tt, n=t<t0?0:Math.min(s.length,1+Math.floor((t-t0)/per));
      $('.txt',b).textContent=s.slice(0,n);
      const focus=t>=t0-0.15 && t<t0+s.length*per+0.1;
      b.classList.toggle('focus',focus);
      $('.caret',b).style.opacity=focus?((t<t0+s.length*per||Math.floor(t*2.4)%2===0)?1:0):0;
      tt=t0+s.length*per+0.2;
    });
    const done=tt;
    const m=$('.hd .m',el); m.style.opacity=EO(P(t,done-0.05,0.25)); m.textContent=fmt(sc.marginNum,ES(P(t,done-0.05,0.7)));
    $$('.fc',el).forEach((f,i)=>rise(f,EO(P(t,done+0.25+i*0.12,0.4)),16));
    rise($('.res .note',el),EO(P(t,done+0.6,0.5)),12);
  },
  end(sc,el,t){
    // Quick build so the whole card (its 18+ line included) is settled by about 0.75 s
    // and then holds still until the loop.
    const k=EO(P(t,sc.t0,0.4)); const lg=$('.elogo',el); lg.style.opacity=k; lg.style.transform=`scale(${0.9+0.1*k})`;
    $$('h1 .w',el).forEach((w,i)=>rise(w,EO(P(t,sc.t0+0.06+i*0.03,0.35)),40));
    rise($('.ebody',el),EO(P(t,sc.t0+0.2,0.35)),24);
    rise($('.url',el),EO(P(t,sc.t0+0.25,0.4)),30);
    rise($('.esub',el),EO(P(t,sc.t0+0.32,0.35)),20);
    rise($('.ehelp',el),EO(P(t,sc.t0+HELP_IN,HELP_RISE)),20);
  },
};
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function seek(t){
  $('#bg').style.transform=`translateY(${-((t*14)%120)}px)`;
  const endSc=D.scenes[D.scenes.length-1];
  // The header logo makes way for the end card's. The header's 18+ stays until the end card's own 18+
  // line has fully risen, so every frame shows 18+.
  $('#head img').style.opacity=1-EO(P(t,endSc.t0-0.1,0.35));
  const ha=1-EO(P(t,endSc.t0+HELP_IN+HELP_RISE,0.35));
  $('#head .pill').style.opacity=ha;
  D.scenes.forEach((sc,i)=>{
    const el=document.getElementById('s'+i);
    const last=i===D.scenes.length-1;
    const a=i===0?1:EO(P(t,sc.t0,0.38)), b=last?1:1-P(t,sc.t1-0.1,0.26);
    const vis=Math.min(a,b);
    if(t<sc.t0-0.01 || (!last && t>sc.t1+0.2)){ el.style.opacity=0; el.style.visibility='hidden'; return; }
    el.style.visibility='visible'; el.style.opacity=vis; el.style.transform=`translateY(${(1-a)*24}px)`;
    U[sc.type](sc,el,t);
  });
  const cap=$('#cap'), c=D.caps.find(c=>t>=c.t0-0.06 && t<c.t1);
  if(!c){ cap.style.opacity=0; return; }
  if(cap.dataset.id!==String(c.id)){ cap.innerHTML='<span class="ln">'+c.words.map(w=>`<span class="cw">${esc(w.w)}</span>`).join(' ')+'</span>'; cap.dataset.id=String(c.id); }
  const k=EO(P(t,c.t0-0.06,0.16)); cap.style.opacity=k; cap.style.transform=`translateY(${(1-k)*10}px)`;
  $$('.cw',cap).forEach((s,i)=>s.classList.toggle('on',t>=c.words[i].t0-0.03));
}
function fit(){
  const bad=[];
  D.scenes.forEach((sc,i)=>{
    const el=document.getElementById('s'+i); el.style.visibility='visible';
    for(const w of $$('.wfit',el)){
      const box=w.parentElement; let size=parseFloat(getComputedStyle(w).fontSize);
      const room=w.classList.contains('v')?box.clientWidth:el.clientWidth;
      while(w.getBoundingClientRect().width>room+1 && size>parseFloat(w.dataset.min)){ size-=2; w.style.fontSize=size+'px'; }
      if(w.getBoundingClientRect().width>room+1) bad.push(`scene ${i+1}: "${w.textContent}" is too wide`);
    }
    const fits=$$('.fit',el);
    for(let n=0;n<90 && el.scrollHeight>el.clientHeight+1;n++){
      let changed=false;
      for(const f of fits){ const s=parseFloat(getComputedStyle(f).fontSize),m=parseFloat(f.dataset.min); if(s>m){ f.style.fontSize=Math.max(m,s-2)+'px'; changed=true; } }
      if(!changed) break;
    }
    if(el.scrollHeight>el.clientHeight+1) bad.push(`scene ${i+1} is too tall`);
    for(const x of $$('*',el)){ if(x.closest('.bar, svg')) continue; const r=x.getBoundingClientRect(); if(r.width && (r.right>80+880+2 || r.left<80-2)) { bad.push(`scene ${i+1}: "${(x.textContent||'').slice(0,30)}" runs off the side`); break; } }
    el.style.visibility='hidden';
  });
  return bad;
}
window.seek=seek; window.fitAll=fit;
"""


def page_html(scenes: list, data: dict) -> str:
    body = "".join(scene_html(i, sc) for i, sc in enumerate(scenes))
    payload = json.dumps(data).replace("</", "<\\/")  # outside the f-string so Python 3.11 can parse this file
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            '<div id="bg"></div><div id="vig"></div>'
            '<div id="head"><img src="brand/xedge-logo-on-dark.svg" alt="xEdge"><div class="pill">18+</div></div>'
            f'{body}<div id="cap"></div><script>{JS.replace("__DATA__", payload)}</script></body></html>')


# ---------------------------------------------------------------- timeline

def build_timeline(spec: dict, work: pathlib.Path, preview: bool) -> dict:
    scenes = spec["scenes"]
    voice = {**DEFAULT_VOICE, **spec.get("voice", {})}
    parsed = [parse_say(sc["say"]) if sc.get("say") else None for sc in scenes]
    # One continuous take: join every scene's line and remember where each one starts.
    offsets, parts, pos = [], [], 0
    for p in parsed:
        offsets.append(pos if p else None)
        if p:
            parts.append(p["spoken"])
            pos += len(p["spoken"]) + 1
    full = " ".join(parts)
    clips, billed = [], 0
    if preview:
        starts, ends, dur = guess_times(full)
    else:
        mp3, starts, ends, billed = narrate(full, voice, work / "voice")
        tempo = float(voice.get("tempo", 1.0))
        dur = decode(mp3, work / "narration.wav", tempo)
        if tempo != 1.0:
            starts, ends = [x / tempo for x in starts], [x / tempo for x in ends]
        clips.append((LEAD, work / "narration.wav"))

    def at(j: int) -> float:
        while j < len(full) - 1 and full[j].isspace():
            j += 1
        return LEAD + starts[min(j, len(full) - 1)]

    def until(j: int) -> float:
        j = min(j, len(full)) - 1
        while j > 0 and full[j].isspace():
            j -= 1
        return LEAD + ends[max(j, 0)]

    speech_end = LEAD + max(ends)
    timeline, caps = [], []
    for i, (sc, p, off) in enumerate(zip(scenes, parsed, offsets)):
        if p:
            entry = {"type": sc["type"], "t0": 0.0 if i == 0 else max(0.0, at(off) - PRE),
                     "beats": [at(off + p["beats"][b]) for b in sorted(p["beats"])]}
            words = [{"w": w["w"], "t0": at(off + w["a"]), "t1": until(off + w["b"])} for w in p["words"]]
            chunk = []
            for w in words:
                text = " ".join(x["w"] for x in chunk + [w])
                if chunk and (len(text) > 22 or re.search(r"[.?!:;]$", chunk[-1]["w"]) or w["t0"] - chunk[-1]["t1"] > 0.45):
                    caps.append(chunk)
                    chunk = []
                chunk.append(w)
            if chunk:
                caps.append(chunk)
        else:
            entry = {"type": sc["type"], "t0": speech_end + END_GAP - PRE, "beats": []}
        timeline.append(entry)
    total = timeline[-1]["t0"] + END_HOLD
    for i, entry in enumerate(timeline):
        entry["t1"] = timeline[i + 1]["t0"] if i + 1 < len(timeline) else total
    cap_list = []
    for n, chunk in enumerate(caps):
        nxt = caps[n + 1][0]["t0"] if n + 1 < len(caps) else total
        cap_list.append({"id": n, "t0": chunk[0]["t0"], "t1": min(chunk[-1]["t1"] + 0.35, nxt - 0.02), "words": chunk})
    for sc, entry in zip(scenes, timeline):
        if sc["type"] == "sum":
            entry["totalNum"] = num_parts(sc["total"])
        if sc["type"] == "number":
            entry["numParts"] = num_parts(sc["number"])
        if sc["type"] == "compare":
            entry["barVals"] = [num_parts(b["value"]) for b in sc["bars"]]
        if sc["type"] == "checker":
            entry["odds"] = [str(o) for o in sc["odds"]]
            entry["marginNum"] = num_parts(sc["_checker"]["margin"])
        if sc["type"] == "hook" and sc.get("visual") == "pitch":
            entry["geo"] = pitch_geometry(HOOK_PITCH, HOOK_PITCH_VIEWBOX, lead=0.05)
        if sc["type"] == "hook" and sc.get("visual") == "goal":
            entry["hv"] = {"from": list(HOOK_GOAL["from"]), "ctrl": list(HOOK_GOAL["ctrl"]), "to": list(HOOK_GOAL["to"]),
                           "cl": curve_lengths(HOOK_GOAL["from"], HOOK_GOAL["ctrl"], HOOK_GOAL["to"])}
        if sc["type"] == "pitch_story":
            entry["geo"] = pitch_geometry(sc)
        if sc["type"] == "match_compare":
            entry.update(compare_numbers(sc))
        if sc["type"] == "probability_pitch":
            entry["shots"] = shot_plan(sc)
        if sc["type"] == "football_stat":
            entry["stat"] = stat_numbers(sc)
    hook = timeline[0]
    n_words = len(re.findall(r"\S+", plain(scenes[0]["title"])))
    cover_t = min(total - 0.1, hook["t0"] + 0.04 * n_words + 0.6)
    return {"scenes": timeline, "caps": cap_list, "total": total, "clips": clips, "billed": billed,
            "cover_t": cover_t, "voice": voice,
            "script": " ".join(p["display"] for p in parsed if p), "spoken": full}


def build_track(clips: list, total: float, out: pathlib.Path) -> None:
    n = int(math.ceil(total * SR))
    buf = bytearray(n * 2)
    for start, path in clips:
        with wave.open(str(path)) as w:
            frames = w.readframes(w.getnframes())
        off = int(round(start * SR)) * 2
        frames = frames[: max(0, len(buf) - off)]
        buf[off:off + len(frames)] = frames
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(buf))


# ---------------------------------------------------------------- render

LOUDNESS = "I=-14:TP=-1.5:LRA=11"  # -14 LUFS, the level TikTok, Reels and Shorts play voice at


def loudnorm_filter(audio: pathlib.Path) -> str:
    """Measure the voice track first, then normalise it with those figures (two passes). A single pass lands
    2 to 3 dB short on a 30-second voiceover, because it has to guess the level as it goes."""
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(audio), "-af",
                        f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if r.returncode != 0 or not m:
        return f"loudnorm={LOUDNESS}"
    j = json.loads(m.group(0))
    return (f"loudnorm={LOUDNESS}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
            f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")


def render(spec: dict, tl: dict, out_mp4: pathlib.Path, cover: pathlib.Path, audio: pathlib.Path | None) -> None:
    data = {"scenes": tl["scenes"], "caps": tl["caps"], "total": tl["total"]}
    frames = int(math.ceil(tl["total"] * FPS))
    with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
        tmp.write(page_html(spec["scenes"], data))
        html_path = pathlib.Path(tmp.name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)
            if not page.evaluate("document.fonts.check(\"800 66px 'Archivo'\") && document.fonts.check(\"500 20px 'Geist Mono'\")"):
                sys.exit("Fonts did not load")
            bad = page.evaluate("fitAll()")
            if bad:
                sys.exit("Refusing to render, text doesn't fit:\n- " + "\n- ".join(bad))
            vf = "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
            cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-"]
            if audio:
                cmd += ["-i", str(audio), "-filter:a", loudnorm_filter(audio) + ",aresample=48000", "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2"]
            else:
                cmd += ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-c:a", "aac", "-b:a", "96k", "-shortest"]
            cmd += ["-filter:v", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-level", "4.2",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", str(FPS),
                    "-t", f"{frames / FPS:.3f}", "-movflags", "+faststart", str(out_mp4)]
            ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            try:
                for f in range(frames):
                    page.evaluate("t => seek(t)", f / FPS)
                    ff.stdin.write(page.screenshot(type="png"))
            finally:
                ff.stdin.close()
                if ff.wait() != 0:
                    sys.exit("ffmpeg failed")
            page.evaluate("t => seek(t)", tl["cover_t"])
            png = page.screenshot(type="png")
            browser.close()
        tmp_png = cover.with_suffix(".png")
        tmp_png.write_bytes(png)
        Image.open(tmp_png).convert("RGB").save(cover, "JPEG", quality=92, optimize=True)
        tmp_png.unlink()
    finally:
        html_path.unlink(missing_ok=True)


def stills(spec: dict, tl: dict, times: list) -> list:
    data = {"scenes": tl["scenes"], "caps": tl["caps"], "total": tl["total"]}
    with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
        tmp.write(page_html(spec["scenes"], data))
        html_path = pathlib.Path(tmp.name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)
            bad = page.evaluate("fitAll()")
            if bad:
                print("Doesn't fit:\n- " + "\n- ".join(bad), file=sys.stderr)
            out = []
            for t in times:
                page.evaluate("t => seek(t)", t)
                out.append(page.screenshot(type="png"))
            browser.close()
            return out
    finally:
        html_path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="JSON file of scenes (keep it outside this repo)")
    ap.add_argument("out_dir", help="output folder, normally videos/YYYY-MM-DD")
    ap.add_argument("--name", required=True, help="file name stem in lowercase-with-hyphens")
    ap.add_argument("--work", required=True, help="working folder outside the repo (voice cache, previews)")
    ap.add_argument("--preview", action="store_true", help="no voice: guessed timings, silent preview in --work")
    ap.add_argument("--stills", help="comma-separated seconds: write those frames as PNGs into --work and stop")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name) or len(a.name) > 48:
        sys.exit("--name must be lowercase letters, digits and hyphens, 48 characters at most")
    work = pathlib.Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repo")
    spec = json.loads(pathlib.Path(a.spec).read_text())
    problems, warnings = check(spec)
    if spec.get("name") and spec["name"] != a.name:
        problems.append(f"--name {a.name} doesn't match the entry's name, {spec['name']}")
    if spec.get("folder") and not a.preview and pathlib.PurePosixPath(a.out_dir).as_posix().rstrip("/") != spec["folder"]:
        problems.append(f"the output folder {a.out_dir} doesn't match the entry's folder, {spec['folder']}")
    if problems:
        sys.exit("Refusing to render:\n- " + "\n- ".join(problems))
    for sc in spec["scenes"]:
        if sc["type"] == "checker":
            sc["_checker"] = checker_numbers(sc["odds"])
    work.mkdir(parents=True, exist_ok=True)
    if a.preview:
        out_mp4, cover = work / f"{a.name}-preview.mp4", work / f"{a.name}-preview-cover.jpg"
    else:
        out_dir = pathlib.Path(a.out_dir)
        out_mp4, cover = out_dir / f"{a.name}.mp4", out_dir / f"{a.name}-cover.jpg"
        taken = [str(p) for p in (out_mp4, cover) if p.exists()]
        if taken:
            sys.exit("Refusing to overwrite (a post may use these): " + ", ".join(taken) + ". Pick another --name.")
    try:
        tl = build_timeline(spec, work, a.preview)
    except VoiceError as e:
        sys.exit(str(e))
    if not 6 <= tl["total"] <= 75:
        sys.exit(f"The video would run {tl['total']:.1f} seconds; keep it between 6 and 75")
    if a.stills:
        times = [float(x) for x in a.stills.split(",")]
        for t, png in zip(times, stills(spec, tl, times)):
            path = work / f"{a.name}-{t:05.2f}s.png"
            path.write_bytes(png)
            print(path)
        return
    audio = None
    if not a.preview:
        audio = work / f"{a.name}-voice.wav"
        build_track(tl["clips"], tl["total"], audio)
    with tempfile.TemporaryDirectory() as staging:
        st_mp4, st_cover = pathlib.Path(staging) / out_mp4.name, pathlib.Path(staging) / cover.name
        render(spec, tl, st_mp4, st_cover, audio)
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(st_mp4), str(out_mp4))
        shutil.move(str(st_cover), str(cover))
    print(json.dumps({
        "video": str(out_mp4), "cover": str(cover), "seconds": round(tl["total"], 2),
        "thumbnail_offset_ms": int(tl["cover_t"] * 1000), "preview": a.preview,
        "voice_id": tl["voice"]["voice_id"], "characters_billed": tl["billed"],
        "script": tl["script"], "warnings": warnings,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

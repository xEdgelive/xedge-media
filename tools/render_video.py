#!/usr/bin/env python3
"""Render an xEdge explainer video (1080x1920, 30 fps H.264 MP4 with AAC voice) from a JSON file of scenes.

Usage:
  python3 tools/render_video.py spec.json videos/YYYY-MM-DD --name the-4-8-you-never-see --work /path/outside/repo
  python3 tools/render_video.py spec.json videos/YYYY-MM-DD --name the-4-8-you-never-see --work /path/outside/repo --preview

The voiceover comes from ElevenLabs' text-to-speech API. The API key is never in this repo,
a file or the command line: the cloud environment's API credential adds it to requests for
api.elevenlabs.io. Voice clips are cached in --work, so a re-render costs no credits.
--preview skips the voice, guesses the timings and writes a silent preview into --work only.

spec.json (keep it outside this repo):
{
  "voice": {"voice_id": "onwK4e9ZLuTAKqWW03F9", "speed": 1.0},
  "scenes": [
    {"type": "hook", "kicker": "PRICE CHECK", "title": "Every match has a [[hidden fee]]",
     "say": "Every football match has a hidden fee."},
    {"type": "prices", "kicker": "ONE MATCH'S ODDS · EXAMPLE", "to_kicker": "AS A CHANCE",
     "tiles": [{"label": "HOME", "value": "11/10", "sub": "2.10", "to": "47.6%", "to_sub": "1 ÷ 2.10"}, ...],
     "say": "These are one match's odds: {1}[11/10|eleven-to-ten], ... Turn each into a chance: {4}47.6, ..."},
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

- 3 to 9 scenes. The first must be a hook and the last an end card. Every scene but the end card has a voice line.
- In "say", [shown|spoken] puts one thing in the captions and has the voice say another (fractional
  odds, the web address). {1}, {2} ... mark the moments the animation steps forward: tiles
  appearing then converting, a total landing, bars growing, list items appearing.
- [[Double brackets]] in a title show those words in the brand colour.
- The checker scene is a copy of the free margin checker on xedge.live, with the same maths
  (the power method), so whatever odds it types give the numbers the real checker shows.
- Every frame carries 18+ and the helpline; the end card adds xedge.live and the full
  National Gambling Helpline line.

It refuses to render if text is too long or doesn't fit, names a bookmaker, uses banned
wording, or would overwrite a video a post may be using. Softer wording matches are printed
as warnings for a person to check against the Rules tab.
"""
import argparse
import hashlib
import html
import json
import math
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
DEFAULT_VOICE = {"voice_id": "onwK4e9ZLuTAKqWW03F9", "model_id": "eleven_multilingual_v2", "speed": 1.0,
                 "stability": 0.5, "similarity_boost": 0.75, "style": 0.0}
LEAD, PRE, GAP, END_HOLD = 0.25, 0.15, 0.35, 3.2

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
    for k in set(d) - {"voice", "scenes"}:
        problems.append(f"{k!r} isn't used")
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
        allowed = set(LIMITS[kind]) | {"type", "pause"} | EXTRA_KEYS.get(kind, set())
        for key in sc:
            if key not in allowed:
                problems.append(f"scene {n}: {key!r} isn't used on a {kind} scene")
        for key, limit in LIMITS[kind].items():
            value = str(sc.get(key, ""))
            size = len(parse_say(value)["display"]) if key == "say" else len(plain(value))
            if size > limit:
                problems.append(f"scene {n}: {key} is {size} characters (limit {limit})")
        if "pause" in sc and not (isinstance(sc["pause"], (int, float)) and 0 <= sc["pause"] <= 1.5):
            problems.append(f"scene {n}: pause must be 0 to 1.5 seconds")
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
        if sc.get("say"):
            p = parse_say(sc["say"])
            if re.search(r"[\[\]{}|]", p["display"]):
                problems.append(f"scene {n}: say has a stray bracket or bar; use [shown|spoken] and {{1}}")
            want = {"prices": 2 * len(sc.get("tiles") or []) if any(isinstance(t, dict) and t.get("to") for t in sc.get("tiles") or []) else len(sc.get("tiles") or []),
                    "sum": 2, "compare": len(sc.get("bars") or []), "list": len(sc.get("items") or [])}.get(kind)
            if p["beats"] and want and sorted(p["beats"]) != list(range(1, len(p["beats"]) + 1)):
                problems.append(f"scene {n}: beats must be numbered {{1}}, {{2}} ... in order")
            if p["beats"] and want and len(p["beats"]) > want:
                problems.append(f"scene {n}: {len(p['beats'])} beats but this scene uses at most {want}")
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


# ---------------------------------------------------------------- voice

class VoiceError(Exception):
    pass


def tts(text: str, prev_text: str, next_text: str, voice: dict, cache: pathlib.Path) -> tuple:
    """Return (mp3 path, alignment dict, characters billed). Cached by everything that shapes the audio."""
    body = {"text": text, "model_id": voice["model_id"], "seed": 4207,
            "voice_settings": {"stability": voice["stability"], "similarity_boost": voice["similarity_boost"],
                               "style": voice["style"], "use_speaker_boost": True, "speed": voice["speed"]}}
    if prev_text:
        body["previous_text"] = prev_text
    if next_text:
        body["next_text"] = next_text
    key = hashlib.sha1(json.dumps([voice["voice_id"], body], sort_keys=True).encode()).hexdigest()[:16]
    mp3, meta = cache / f"{key}.mp3", cache / f"{key}.json"
    if mp3.exists() and meta.exists():
        return mp3, json.loads(meta.read_text()), 0
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice['voice_id']}/with-timestamps"
           f"?output_format=mp3_44100_128")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (401, 403):
            raise VoiceError(f"ElevenLabs refused the request ({e.code}): {detail}\nCheck the ElevenLabs API credential "
                             "on the cloud environment (host api.elevenlabs.io, header xi-api-key) and that the key "
                             "allows Text to Speech and has credits left.")
        raise VoiceError(f"ElevenLabs error {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise VoiceError(f"Couldn't reach api.elevenlabs.io ({e}). The cloud environment needs the ElevenLabs API credential.")
    cache.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    meta.write_text(json.dumps(data.get("alignment") or data.get("normalized_alignment")))
    return mp3, json.loads(meta.read_text()), len(text)


def decode(mp3: pathlib.Path, out: pathlib.Path) -> float:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR),
                    "-c:a", "pcm_s16le", str(out)], check=True)
    with wave.open(str(out)) as w:
        return w.getnframes() / SR


def char_times(spoken: str, alignment: dict, duration: float) -> tuple:
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if "".join(chars) == spoken and len(starts) == len(spoken):
        return starts, ends
    # Fall back to spreading the characters through the clip if the alignment doesn't line up.
    n = max(1, len(spoken))
    return [duration * i / n for i in range(n)], [duration * (i + 1) / n for i in range(n)]


def guess_times(spoken: str) -> tuple:
    rate = 15.0  # characters a second, roughly ElevenLabs' pace at speed 1.0
    starts = [i / rate for i in range(len(spoken))]
    return starts, [s + 1 / rate for s in starts], len(spoken) / rate + 0.15


# ---------------------------------------------------------------- page

def rich_words(text: str) -> str:
    """Words as animatable spans; [[words]] in the brand colour."""
    out, hl = [], False
    for part in re.split(r"(\[\[|\]\])", text):
        if part == "[[":
            hl = True
        elif part == "]]":
            hl = False
        else:
            for w in part.split():
                out.append(f'<span class="w{" hl" if hl else ""}">{html.escape(w)}</span>')
    return " ".join(out)


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
                 f'<div class="fair">{fair}</div><p class="note">Fair odds are the market’s odds with the bookmaker’s margin removed, not xEdge’s model prices.</p></div></div>')
    elif kind == "end":
        body = f'<p class="ebody">{e(sc["body"])}</p>' if sc.get("body") else ""
        inner = (f'<img class="elogo" src="brand/xedge-logo-on-dark.svg" alt="xEdge"><h1 class="fit" data-min="56">{rich_words(sc["title"])}</h1>{body}'
                 '<div class="url">xedge.live</div><div class="esub">FREE MARGIN CHECKER · WAITLIST · UK ONLY</div>'
                 '<div class="ehelp">18+ · Gambling help:<br>National Gambling Helpline 0808 8020 133</div>')
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
#help{position:absolute;left:80px;top:272px;font-family:'Geist Mono';font-weight:500;font-size:22px;letter-spacing:.08em;color:var(--label)}
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
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
function rise(el,k,dy=30){ if(!el) return; el.style.opacity=k; el.style.transform=`translateY(${(1-k)*dy}px)`; }
function fmt(n,k){ return n.pre+(n.num*k).toFixed(n.dec)+n.suf; }
function beat(sc,i,fallback){ const b=sc.beats[i]; return (b===undefined||b===null)?fallback:b; }
const U = {
  hook(sc,el,t){
    rise($('.kicker',el),EO(P(t,sc.t0,0.5)),20);
    $$('.w',el).forEach((w,i)=>rise(w,EO(P(t,sc.t0+0.06+i*0.07,0.55)),56));
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
    const max=Math.max(110,Math.ceil(sc.totalNum.num/10)*10+5), Wd=bar.clientWidth;
    const cur=sc.totalNum.num*g;
    $('.f1',bar).style.width=(Math.min(cur,100)/max*Wd)+'px';
    const f2=$('.f2',bar); f2.style.left=(100/max*Wd)+'px'; f2.style.width=(Math.max(0,cur-100)/max*Wd)+'px';
    $('.mark',bar).style.left=(100/max*Wd)+'px';
    const ml=$('.mlab',bar); ml.style.left=(100/max*Wd+2)+'px'; ml.style.opacity=EO(P(t,beat(sc,1,tb+0.9)-0.1,0.4));
    const ol=$('.olab',bar);
    if(sc.totalNum.num>100){ ol.textContent='+'+(sc.totalNum.num-100).toFixed(sc.totalNum.dec)+'%';
      ol.style.left=((100+(sc.totalNum.num-100)/2)/max*Wd)+'px'; ol.style.opacity=EO(P(t,tb+0.75,0.35)); } else ol.style.opacity=0;
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
    const k=EO(P(t,sc.t0+0.02,0.6)); const lg=$('.elogo',el); lg.style.opacity=k; lg.style.transform=`scale(${0.9+0.1*k})`;
    $$('h1 .w',el).forEach((w,i)=>rise(w,EO(P(t,sc.t0+0.15+i*0.06,0.5)),40));
    rise($('.ebody',el),EO(P(t,sc.t0+0.45,0.5)),24);
    rise($('.url',el),EO(P(t,sc.t0+0.55,0.55)),30);
    rise($('.esub',el),EO(P(t,sc.t0+0.7,0.5)),20);
    rise($('.ehelp',el),EO(P(t,sc.t0+0.85,0.5)),20);
  },
};
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function seek(t){
  $('#bg').style.transform=`translateY(${-((t*14)%120)}px)`;
  const endSc=D.scenes[D.scenes.length-1];
  const ha=1-EO(P(t,endSc.t0-0.1,0.35));
  $('#head').style.opacity=ha; $('#help').style.opacity=ha;
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
    for(const x of $$('*',el)){ if(x.closest('.bar')) continue; const r=x.getBoundingClientRect(); if(r.width && (r.right>80+880+2 || r.left<80-2)) { bad.push(`scene ${i+1}: "${(x.textContent||'').slice(0,30)}" runs off the side`); break; } }
    el.style.visibility='hidden';
  });
  return bad;
}
window.seek=seek; window.fitAll=fit;
"""


def page_html(scenes: list, data: dict) -> str:
    body = "".join(scene_html(i, sc) for i, sc in enumerate(scenes))
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            '<div id="bg"></div><div id="vig"></div>'
            '<div id="head"><img src="brand/xedge-logo-on-dark.svg" alt="xEdge"><div class="pill">18+</div></div>'
            '<div id="help">GAMBLING HELP · 0808 8020 133</div>'
            f'{body}<div id="cap"></div><script>{JS.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))}</script></body></html>')


# ---------------------------------------------------------------- timeline

def build_timeline(spec: dict, work: pathlib.Path, preview: bool) -> dict:
    scenes = spec["scenes"]
    voice = {**DEFAULT_VOICE, **spec.get("voice", {})}
    parsed = [parse_say(sc["say"]) if sc.get("say") else None for sc in scenes]
    said = [p["spoken"] for p in parsed if p]
    clips, billed, t = [], 0, LEAD
    timeline, caps = [], []
    k = 0
    for i, (sc, p) in enumerate(zip(scenes, parsed)):
        entry = {"type": sc["type"], "beats": [], "t0": 0.0 if i == 0 else max(0.0, t - PRE)}
        if p:
            if preview:
                starts, ends, dur = guess_times(p["spoken"])
            else:
                mp3, align, cost = tts(p["spoken"], " ".join(said[:k])[-400:], " ".join(said[k + 1:])[:400], voice, work / "voice")
                billed += cost
                dur = decode(mp3, work / f"clip-{i}.wav")
                starts, ends = char_times(p["spoken"], align, dur)
                clips.append((t, work / f"clip-{i}.wav"))
            k += 1
            s = p["spoken"]

            def at(j, starts=starts, s=s, base=t):
                while j < len(s) and s[j].isspace():
                    j += 1
                return base + (starts[min(j, len(starts) - 1)] if starts else 0)

            def until(j, ends=ends, s=s, base=t):
                j = min(j, len(s)) - 1
                while j > 0 and s[j].isspace():
                    j -= 1
                return base + (ends[max(j, 0)] if ends else 0)

            entry["beats"] = [at(p["beats"][b]) for b in sorted(p["beats"])]
            words = [{"w": w["w"], "t0": at(w["a"]), "t1": until(w["b"])} for w in p["words"]]
            chunk = []
            for w in words:
                text = " ".join(x["w"] for x in chunk + [w])
                if chunk and (len(text) > 22 or re.search(r"[.?!:;]$", chunk[-1]["w"]) or w["t0"] - chunk[-1]["t1"] > 0.45):
                    caps.append(chunk)
                    chunk = []
                chunk.append(w)
            if chunk:
                caps.append(chunk)
            t = t + dur + float(sc.get("pause", GAP))
        entry["t_end_voice"] = t
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
    hook = timeline[0]
    n_words = len(re.findall(r"\S+", plain(scenes[0]["title"])))
    cover_t = min(total - 0.1, hook["t0"] + 0.06 + 0.07 * n_words + 0.6)
    return {"scenes": timeline, "caps": cap_list, "total": total, "clips": clips, "billed": billed,
            "cover_t": cover_t, "voice": voice,
            "script": " ".join(p["display"] for p in parsed if p), "spoken": " ".join(said)}


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

def render(spec: dict, tl: dict, out_mp4: pathlib.Path, cover: pathlib.Path, audio: pathlib.Path | None) -> None:
    data = {"scenes": tl["scenes"], "caps": tl["caps"], "total": tl["total"]}
    frames = int(math.ceil(tl["total"] * FPS))
    with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
        tmp.write(page_html(spec["scenes"], data))
        html_path = pathlib.Path(tmp.name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
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
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-"]
            if audio:
                cmd += ["-i", str(audio), "-filter:a", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2"]
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
            browser = p.chromium.launch()
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

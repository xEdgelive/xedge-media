#!/usr/bin/env python3
"""Render an xEdge Instagram carousel (1080x1350 slides) from a JSON file of slides.

Usage:
  python3 tools/render_carousel.py slides.json cards/YYYY-MM-DD --name odds-are-chances

Writes <name>-01.jpg, <name>-02.jpg and so on into the output folder, then prints
JSON with the file paths, each slide's alt text and any wording warnings.

slides.json (keep it outside this repo):
{
  "slides": [
    {"type": "cover",  "kicker": "HOW ODDS WORK", "title": "Odds are [[chances]] in disguise",
     "body": "Swipe to turn any price into a percentage"},
    {"type": "text",   "title": "Decimal odds", "body": "Divide 1 by the price.", "math": "1 ÷ 2.10 = 47.6%"},
    {"type": "number", "number": "4.8%", "title": "The bookmaker's margin", "body": "..."},
    {"type": "list",   "title": "Five checks", "items": ["...", "..."]},
    {"type": "end",    "title": "Check any match free", "body": "..."}
  ]
}

- 2 to 10 slides. The first must be a cover and the last an end slide.
- [[Double brackets]] in a title or a number slide's number mark words to show in the
  brand colour. In "math", everything after the last "=" is highlighted.
- Any slide may carry "note": one line of small print, such as where prices came from.
- Every slide gets the 18+ badge and the helpline. The end slide adds xedge.live.

It refuses to render if a slide is too long, names a bookmaker or uses banned wording,
or if a file of the same name already exists (a post may be using it). Softer wording
matches are printed as warnings for a person to check against the Rules tab.
"""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chromium import launch as launch_chromium  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 1080, 1350

# Characters allowed per field, by slide type.
LIMITS = {
    "cover": {"kicker": 40, "title": 80, "body": 140},
    "text": {"title": 90, "body": 280, "math": 40},
    "number": {"number": 8, "title": 90, "body": 220, "math": 40},
    "list": {"title": 70, "item": 100},
    "end": {"title": 70, "body": 160},
}
REQUIRED = {"cover": ["title"], "text": ["title"], "number": ["number", "title"], "list": ["title", "items"], "end": ["title"]}
NOTE_LIMIT = 140

# Never on a card: UK bookmaker and exchange names (the Rules tab bans naming any).
BOOKMAKERS = [
    "bet365", "betfair", "betfred", "betvictor", "bet victor", "betway", "boylesports", "boyle sports",
    "coral", "ladbrokes", "paddy power", "paddypower", "sky bet", "skybet", "william hill", "williamhill",
    "unibet", "888sport", "888 sport", "livescore bet", "livescorebet", "virgin bet", "virginbet",
    "smarkets", "matchbook", "grosvenor", "leovegas", "leo vegas", "casumo", "mr green", "mrgreen",
    "midnite", "kwiff", "betuk", "spreadex", "sporting index", "star sports", "quinnbet", "betgoodwin",
    "talksport bet", "betmgm", "bet mgm", "fanteam", "parimatch", "bwin", "sportingbet", "betano",
    "10bet", "dafabet", "pinnacle", "sbobet", "bet442", "betsson", "fitzdares", "tote",
]
# Never on a card: wording the Rules tab and the CAP Code rule out in any context.
BANNED = [
    r"bet now", r"free bets?", r"sure thing", r"easy money", r"beat(ing)? the bookies?", r"can'?t lose",
    r"cannot lose", r"risk[- ]free", r"no[- ]lose", r"nailed on", r"banker", r"get rich", r"second income",
    r"quit (your|the) job", r"hurry", r"last chance", r"act now", r"don'?t miss", r"today only",
    r"limited time", r"before it'?s too late",
]
# Allowed in context ("Do they call profit typical or guaranteed? Walk away."), so only flagged.
WARN = [
    r"guarantee\w*", r"profits?", r"profitable", r"lock", r"tips?", r"winners?", r"winnings", r"roi",
    r"yield", r"returns?", r"value bets?",
]


def words_in(slide: dict) -> str:
    parts = [str(slide.get(k, "")) for k in ("kicker", "title", "body", "number", "math", "note")]
    parts += [str(i) for i in slide.get("items", [])]
    return " ".join(parts)


def plain(text: str) -> str:
    return re.sub(r"\[\[(.+?)\]\]", r"\1", text)


def check(d: dict) -> tuple:
    """Return (problems, warnings); no problems means the slides can be rendered."""
    problems, warnings = [], []
    slides = d.get("slides")
    if not isinstance(slides, list) or not 2 <= len(slides) <= 10:
        return ["there must be 2 to 10 slides"], warnings
    if not isinstance(slides[0], dict) or slides[0].get("type") != "cover":
        problems.append("slide 1 must be a cover")
    if not isinstance(slides[-1], dict) or slides[-1].get("type") != "end":
        problems.append(f"slide {len(slides)} must be an end slide")
    for n, s in enumerate(slides, 1):
        if not isinstance(s, dict):
            problems.append(f"slide {n}: not a slide object")
            continue
        kind = s.get("type")
        if kind not in LIMITS:
            problems.append(f"slide {n}: unknown type {kind!r}")
            continue
        if n not in (1, len(slides)) and kind in ("cover", "end"):
            problems.append(f"slide {n}: a {kind} slide can only come {'first' if kind == 'cover' else 'last'}")
        for key in REQUIRED[kind]:
            if not s.get(key):
                problems.append(f"slide {n}: missing {key}")
        allowed = set(LIMITS[kind]) | {"type", "note"} | ({"items"} if kind == "list" else set())
        allowed.discard("item")
        for key in s:
            if key not in allowed:
                problems.append(f"slide {n}: {key!r} isn't used on a {kind} slide")
        for key, limit in LIMITS[kind].items():
            if key == "item":
                items = s.get("items") or []
                if not 2 <= len(items) <= 5:
                    problems.append(f"slide {n}: a list needs 2 to 5 items")
                for i, item in enumerate(items, 1):
                    if len(str(item)) > limit:
                        problems.append(f"slide {n}: item {i} is {len(str(item))} characters (limit {limit})")
            elif len(plain(str(s.get(key, "")))) > limit:
                problems.append(f"slide {n}: {key} is {len(plain(str(s[key])))} characters (limit {limit})")
        if len(str(s.get("note", ""))) > NOTE_LIMIT:
            problems.append(f"slide {n}: note is over {NOTE_LIMIT} characters")
        text = plain(words_in(s)).lower().replace("’", "'").replace("‘", "'")
        for name in BOOKMAKERS:
            if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                problems.append(f"slide {n}: names a bookmaker ({name})")
        for pattern in BANNED:
            m = re.search(rf"\b{pattern}\b", text)
            if m:
                problems.append(f"slide {n}: banned wording ({m.group(0)!r})")
        for pattern in WARN:
            m = re.search(rf"\b{pattern}\b", text)
            if m:
                warnings.append(f"slide {n}: check the context of {m.group(0)!r}")
    return problems, warnings


def rich(text: str) -> str:
    """Escape text and turn [[words]] into highlighted spans."""
    return re.sub(r"\[\[(.+?)\]\]", r'<span class="hl">\1</span>', html.escape(text))


def math_html(text: str) -> str:
    if "=" not in text:
        return html.escape(text)
    left, right = text.rsplit("=", 1)
    return f'{html.escape(left)}= <b>{html.escape(right.strip())}</b>'


def slide_html(s: dict, n: int, total: int) -> str:
    e = html.escape
    kind = s["type"]
    inner = []
    if kind == "cover":
        if s.get("kicker"):
            inner.append(f'<div class="kicker">{e(s["kicker"].upper())}</div>')
        inner.append(f'<h1 class="fit" data-min="64">{rich(s["title"])}</h1>')
        if s.get("body"):
            inner.append(f'<p class="body fit" data-min="28">{e(s["body"])}</p>')
        inner.append('<div class="swipe">SWIPE <span>&rarr;</span></div>')
    elif kind == "text":
        inner.append(f'<div class="step">{n - 1:02d}</div>')
        inner.append(f'<h1 class="fit" data-min="48">{rich(s["title"])}</h1>')
        if s.get("body"):
            inner.append(f'<p class="body fit" data-min="28">{e(s["body"])}</p>')
        if s.get("math"):
            inner.append(f'<div class="math wfit" data-min="30">{math_html(s["math"])}</div>')
    elif kind == "number":
        inner.append(f'<div class="big wfit" data-min="110">{rich(s["number"])}</div>')
        inner.append(f'<h1 class="fit" data-min="40">{rich(s["title"])}</h1>')
        if s.get("body"):
            inner.append(f'<p class="body fit" data-min="28">{e(s["body"])}</p>')
        if s.get("math"):
            inner.append(f'<div class="math wfit" data-min="30">{math_html(s["math"])}</div>')
    elif kind == "list":
        inner.append(f'<h1 class="fit" data-min="44">{rich(s["title"])}</h1>')
        items = "".join(f'<li><span>{i}</span><div class="fit" data-min="26">{e(str(t))}</div></li>'
                        for i, t in enumerate(s["items"], 1))
        inner.append(f'<ol class="items">{items}</ol>')
    elif kind == "end":
        inner.append(f'<h1 class="fit" data-min="48">{rich(s["title"])}</h1>')
        if s.get("body"):
            inner.append(f'<p class="body fit" data-min="28">{e(s["body"])}</p>')
        inner.append('<div class="cta"><div class="url">xedge.live</div>'
                     '<div class="sub">FREE MARGIN CHECKER · WAITLIST · UK ONLY</div></div>')
    note = f'<div class="note">{e(s["note"])}</div>' if s.get("note") else ""
    help_line = ("18+ · Gambling help: National Gambling Helpline 0808 8020 133" if kind == "end"
                 else "18+ · Gambling help: 0808 8020 133")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Archivo';src:url('fonts/archivo-variable.woff2') format('woff2-variations');font-weight:100 900;font-stretch:62% 125%}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-400.woff2') format('woff2');font-weight:400}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-500.woff2') format('woff2');font-weight:500}}
:root{{--pitch:#0C0E0D;--volt:#C8F53A;--chalk:#F3F5EF;--stone:#A3A8A1;--label:#8A8F88;--faint:#6B7069;--dim:#5B615C;--grid:#1D211F;--pill:#343936;--divider:#232826;--panel:#131715}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;background:var(--pitch)}}
body{{font-family:'Archivo',sans-serif;color:var(--chalk);-webkit-font-smoothing:antialiased}}
.card{{width:{W}px;height:{H}px;padding:64px 72px 56px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;height:48px}}
.top img{{height:40px;display:block}}
.tr{{display:flex;align-items:center;gap:22px}}
.count{{font-family:'Geist Mono';font-weight:500;font-size:20px;letter-spacing:.08em;color:var(--faint)}}
.pill{{font-family:'Geist Mono';font-weight:500;font-size:20px;letter-spacing:.08em;color:var(--stone);border:2px solid var(--pill);border-radius:999px;padding:7px 16px 6px}}
.main{{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:safe center;overflow:hidden;padding:56px 0 40px}}
.cover .main{{justify-content:flex-end;padding-bottom:56px}}
.kicker{{font-family:'Geist Mono';font-weight:500;font-size:24px;letter-spacing:.1em;color:var(--label);margin-bottom:30px}}
h1{{font-weight:800;font-stretch:125%;line-height:1.04;letter-spacing:-.01em;font-size:84px}}
.cover h1{{font-size:100px;line-height:1}}
.number h1{{font-size:56px;line-height:1.08}}
.list h1{{font-size:68px}}
.end h1{{font-size:76px}}
.hl{{color:var(--volt)}}
.body{{font-size:40px;line-height:1.36;color:var(--stone);margin-top:36px;max-width:900px}}
.cover .body{{margin-top:36px}}
.step{{font-family:'Geist Mono';font-weight:500;font-size:28px;letter-spacing:.08em;color:var(--volt);margin-bottom:30px}}
.math{{margin-top:48px;align-self:flex-start;white-space:nowrap;font-family:'Geist Mono';font-weight:500;font-size:48px;color:var(--chalk);background:var(--panel);border:2px solid var(--grid);border-radius:20px;padding:26px 36px}}
.math b{{color:var(--volt);font-weight:500}}
.big{{font-weight:800;font-stretch:112%;font-size:230px;line-height:.92;color:var(--volt);letter-spacing:-.03em;white-space:nowrap;margin-bottom:40px}}
.big .hl{{color:var(--chalk)}}
.items{{list-style:none;margin-top:44px;border-top:1px solid var(--divider)}}
.items li{{display:grid;grid-template-columns:76px 1fr;align-items:baseline;padding:26px 0;border-bottom:1px solid var(--divider)}}
.items li span{{font-family:'Geist Mono';font-weight:500;font-size:28px;color:var(--volt)}}
.items li div{{font-size:36px;line-height:1.3;font-weight:500}}
.swipe{{font-family:'Geist Mono';font-weight:500;font-size:22px;letter-spacing:.12em;color:var(--label);margin-top:64px}}
.swipe span{{color:var(--volt)}}
.cta{{margin-top:64px;padding-top:40px;border-top:1px solid var(--divider)}}
.cta .url{{font-weight:800;font-stretch:125%;font-size:88px;line-height:1;color:var(--volt)}}
.cta .sub{{font-family:'Geist Mono';font-weight:500;font-size:22px;letter-spacing:.08em;color:var(--label);margin-top:18px}}
.note{{font-family:'Geist Mono';font-size:19px;line-height:1.5;color:var(--label);margin-bottom:18px}}
.foot{{border-top:1px solid var(--divider);padding-top:20px;display:flex;justify-content:space-between;font-family:'Geist Mono';font-size:19px;color:var(--stone)}}
.foot .site{{color:var(--label)}}
</style></head><body><div class="card {kind}">
<div class="top"><img src="brand/xedge-logo-on-dark.svg" alt="xEdge"><div class="tr"><div class="count">{n:02d}/{total:02d}</div><div class="pill">18+</div></div></div>
<div class="main">{"".join(inner)}</div>
{note}<div class="foot"><span>{e(help_line)}</span><span class="site">xedge.live</span></div>
</div></body></html>"""


# Shrinks marked text until it fits, then reports anything still overflowing.
FIT_JS = """() => {
  const main = document.querySelector('.main');
  for (const el of document.querySelectorAll('.wfit')) {
    let size = parseFloat(getComputedStyle(el).fontSize);
    const room = main.clientWidth;
    while (el.getBoundingClientRect().width > room && size > parseFloat(el.dataset.min)) {
      size -= 2; el.style.fontSize = size + 'px';
    }
  }
  const fits = [...document.querySelectorAll('.fit')];
  for (let i = 0; i < 80 && main.scrollHeight > main.clientHeight + 1; i++) {
    let changed = false;
    for (const el of fits) {
      const size = parseFloat(getComputedStyle(el).fontSize), min = parseFloat(el.dataset.min);
      if (size > min) { el.style.fontSize = Math.max(min, size - 2) + 'px'; changed = true; }
    }
    if (!changed) break;
  }
  const card = document.querySelector('.card').getBoundingClientRect();
  const wide = main.scrollWidth > main.clientWidth + 2 || [...document.querySelectorAll('.card *')].some(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0) return false;
    if (r.right > card.right - 72 + 1 || r.left < card.left + 72 - 1) return true;
    return el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
  });
  return {tall: main.scrollHeight > main.clientHeight + 1, wide};
}"""


def alt_text(s: dict, n: int, total: int) -> str:
    bits = [s.get("kicker", "").capitalize() if s.get("kicker") else "", plain(s.get("number", "")),
            plain(s.get("title", "")), s.get("body", ""), s.get("math", "")]
    bits += [f"{i}. {t}" for i, t in enumerate(s.get("items", []), 1)]
    if s["type"] == "end":
        bits.append("Free margin checker and waitlist at xedge.live")
    text = " ".join(b.strip() if b.strip()[-1] in ".?!" else b.strip() + "." for b in bits if b and b.strip())
    return f"Slide {n} of {total}. {text} 18+. Gambling help: 0808 8020 133."


def render_all(slides: list, paths: list) -> None:
    """Render every slide into a staging folder; move them into place only if all succeed."""
    with tempfile.TemporaryDirectory() as staging:
        staged = [pathlib.Path(staging) / p.name for p in paths]
        render_into(slides, staged)
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        for src, dst in zip(staged, paths):
            shutil.move(str(src), str(dst))


def render_into(slides: list, paths: list) -> None:
    tmp_files = []
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            for n, (s, out_path) in enumerate(zip(slides, paths), 1):
                with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
                    tmp.write(slide_html(s, n, len(slides)))
                    html_path = pathlib.Path(tmp.name)
                png_path = html_path.with_suffix(".png")
                tmp_files += [html_path, png_path]
                page.goto(html_path.as_uri())
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(150)
                fonts_ok = page.evaluate("document.fonts.check(\"800 66px 'Archivo'\") && document.fonts.check(\"500 20px 'Geist Mono'\")")
                if not fonts_ok:
                    sys.exit("Fonts did not load")
                fit = page.evaluate(FIT_JS)
                if fit["tall"] or fit["wide"]:
                    sys.exit(f"Slide {n} doesn't fit even at the smallest text size; shorten it")
                page.screenshot(path=str(png_path))
                img = Image.open(png_path).convert("RGB").resize((W, H), Image.LANCZOS)
                img.save(out_path, "JPEG", quality=92, optimize=True)
            browser.close()
    finally:
        for f in tmp_files:
            f.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slides", help="JSON file of slides (keep it outside this repo)")
    ap.add_argument("out_dir", help="output folder, normally cards/YYYY-MM-DD")
    ap.add_argument("--name", required=True, help="file name stem in lowercase-with-hyphens, e.g. odds-are-chances")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name) or len(a.name) > 40:
        sys.exit("--name must be lowercase letters, digits and hyphens, 40 characters at most")
    d = json.loads(pathlib.Path(a.slides).read_text())
    problems, warnings = check(d)
    if problems:
        sys.exit("Refusing to render:\n- " + "\n- ".join(problems))
    slides = d["slides"]
    out_dir = pathlib.Path(a.out_dir)
    paths = [out_dir / f"{a.name}-{n:02d}.jpg" for n in range(1, len(slides) + 1)]
    taken = [str(p) for p in out_dir.glob(f"{a.name}-[0-9][0-9].jpg")]
    if taken:
        sys.exit("Refusing to overwrite (a post may use these): " + ", ".join(sorted(taken)) + ". Pick another --name.")
    render_all(slides, paths)
    total = len(slides)
    print(json.dumps({
        "files": [str(p) for p in paths],
        "alt_text": [alt_text(s, n, total) for n, s in enumerate(slides, 1)],
        "warnings": warnings,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

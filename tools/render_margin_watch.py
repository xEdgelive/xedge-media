#!/usr/bin/env python3
"""Render xEdge's Margin Watch card from a JSON file of figures.

Usage:
  python3 tools/render_margin_watch.py figures.json cards/YYYY-MM-DD

Writes margin-watch-feed.jpg (1080x1350, Instagram feed and X) and
margin-watch-story.jpg (1080x1920, Instagram Story) into the output folder,
then prints JSON with the file paths and the image alt text.

figures.json (built from the Margin Watch query; keep it out of this public repo):
{
  "competition": "Premier League",
  "captured_uk": "09:00 Fri 9 Oct",
  "source": "The Odds API",
  "bookmakers": 18,
  "overall_avg_pct": "6.84",
  "rows": [{"home": "...", "away": "...", "kickoff_uk": "Sat 10 Oct 15:00",
            "books": 18, "low_pct": "3.99", "avg_pct": "6.61", "high_pct": "8.33"}, ...]
}
Rows must be sorted from the lowest average margin to the highest.
The script refuses to render if a figure fails the sanity checks below.
"""
import argparse
import html
import json
import math
import pathlib
import re
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chromium import launch as launch_chromium  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Shorter names so every row fits on one line. Unknown names pass through unchanged.
SHORT = {
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton",
    "Coventry City": "Coventry",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Norwich City": "Norwich",
    "Nottingham Forest": "Nott'm Forest",
    "Sheffield United": "Sheffield Utd",
    "Tottenham Hotspur": "Tottenham",
    "West Bromwich Albion": "West Brom",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}

# Story padding keeps everything out of the top and bottom 270px, where Instagram's
# profile bar and reply box sit, so the 18+ and helpline lines are never covered.
FORMATS = {
    "feed": {"w": 1080, "h": 1350, "row": 56, "pt": 60, "pb": 54},
    "story": {"w": 1080, "h": 1920, "row": 58, "pt": 270, "pb": 270},
}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def one_dp(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def short(name: str) -> str:
    return SHORT.get(name, name)


def check(d: dict) -> list:
    """Return a list of problems; an empty list means the figures look sane."""
    problems = []
    rows = d.get("rows") or []
    if not rows:
        problems.append("no matches")
    for key in ("competition", "captured_uk", "source", "bookmakers", "overall_avg_pct"):
        if key not in d:
            problems.append(f"missing {key}")
    last_avg = -1.0
    for r in rows:
        label = f'{r.get("home")} v {r.get("away")}'
        try:
            lo, avg, hi = float(r["low_pct"]), float(r["avg_pct"]), float(r["high_pct"])
        except (KeyError, ValueError):
            problems.append(f"{label}: missing or bad margin")
            continue
        if not (2 <= lo <= avg <= hi <= 15):
            problems.append(f"{label}: margins {lo}/{avg}/{hi} outside 2-15% or out of order")
        if int(r.get("books", 0)) < 10:
            problems.append(f"{label}: only {r.get('books')} bookmakers")
        if avg < last_avg:
            problems.append(f"{label}: rows not sorted by average margin")
        last_avg = avg
        if not re.match(r"^\w{3} \d{1,2} \w{3} \d{2}:\d{2}$", r.get("kickoff_uk", "")):
            problems.append(f"{label}: kickoff_uk should look like 'Sat 10 Oct 15:00'")
    return problems


def date_span(rows, upper: bool = True) -> str:
    days = []
    for r in rows:
        _, day, mon, _ = r["kickoff_uk"].split(" ")
        m = MONTHS.index(mon.upper()) + 1
        days.append((m if m >= 7 else m + 12, int(day), mon.upper() if upper else mon.title()))
    first, last = min(days), max(days)
    if first == last:
        return f"{first[1]} {first[2]}"
    if first[2] == last[2]:
        return f"{first[1]}–{last[1]} {last[2]}"
    return f"{first[1]} {first[2]} – {last[1]} {last[2]}"


def alt_text(d: dict) -> str:
    rows = d["rows"]
    lo, hi = rows[0], rows[-1]
    return (
        f'Margin Watch, {d["competition"]}, {date_span(rows, upper=False).replace(chr(8211), " to ")}. '
        f'Average bookmaker margin on the match result: {one_dp(d["overall_avg_pct"])}% across '
        f'{len(rows)} matches and {d["bookmakers"]} UK bookmakers. Lowest: {short(lo["home"])} v '
        f'{short(lo["away"])}, {one_dp(lo["avg_pct"])}%. Highest: {short(hi["home"])} v '
        f'{short(hi["away"])}, {one_dp(hi["avg_pct"])}%. Prices at {d["captured_uk"]}. 18+.'
    )


def build_html(d: dict, fmt: str) -> str:
    f = FORMATS[fmt]
    rows = d["rows"]
    lo = math.floor(min(float(r["low_pct"]) for r in rows))
    hi = math.ceil(max(float(r["high_pct"]) for r in rows))
    if hi - lo < 4:
        hi = lo + 4
    ticks = [t for t in range(lo, hi + 1) if t % 2 == 0]

    def x(v: float) -> str:
        return f"{(v - lo) / (hi - lo) * 100:.3f}%"

    e = html.escape
    tick_html = "".join(f'<span style="left:{x(t)}">{t}%</span>' for t in ticks)
    grid_html = "".join(f'<i style="left:{x(t)}"></i>' for t in ticks)
    row_html = []
    for r in rows:
        name = f'{e(short(r["home"]))} <em>v</em> {e(short(r["away"]))}'
        day, _, _, time = r["kickoff_uk"].split(" ")
        lo_v, avg_v, hi_v = float(r["low_pct"]), float(r["avg_pct"]), float(r["high_pct"])
        row_html.append(
            f'<div class="row"><div><div class="m">{name}</div><div class="k">{e(day.upper())} {e(time)}</div></div>'
            f'<div class="plot"><b class="rng" style="left:{x(lo_v)};width:calc({x(hi_v)} - {x(lo_v)})"></b>'
            f'<b class="dot" style="left:{x(avg_v)}"></b></div>'
            f'<div class="v">{one_dp(r["avg_pct"])}%</div></div>'
        )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Archivo';src:url('fonts/archivo-variable.woff2') format('woff2-variations');font-weight:100 900;font-stretch:62% 125%}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-400.woff2') format('woff2');font-weight:400}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-500.woff2') format('woff2');font-weight:500}}
:root{{--pitch:#0C0E0D;--volt:#C8F53A;--chalk:#F3F5EF;--stone:#A3A8A1;--label:#8A8F88;--faint:#6B7069;--dim:#5B615C;--grid:#1D211F;--pill:#343936;--divider:#232826}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{f["w"]}px;height:{f["h"]}px;background:var(--pitch)}}
body{{font-family:'Archivo',sans-serif;color:var(--chalk);-webkit-font-smoothing:antialiased}}
.card{{width:{f["w"]}px;height:{f["h"]}px;padding:{f["pt"]}px 64px {f["pb"]}px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center}}
.top img{{height:40px;display:block}}
.pill{{font-family:'Geist Mono';font-weight:500;font-size:20px;letter-spacing:.08em;color:var(--stone);border:2px solid var(--pill);border-radius:999px;padding:7px 16px 6px}}
.label{{font-family:'Geist Mono';font-weight:500;font-size:21px;letter-spacing:.08em;color:var(--label);margin-top:48px}}
.label b{{color:var(--chalk);font-weight:500}}
h1{{font-weight:800;font-stretch:125%;font-size:54px;line-height:1.06;margin-top:16px;max-width:900px}}
.hero{{display:flex;align-items:center;gap:32px;margin-top:30px}}
.num{{font-weight:800;font-stretch:125%;font-size:148px;line-height:.9;color:var(--volt);letter-spacing:-.02em}}
.cap{{font-size:26px;line-height:1.35;color:var(--stone);max-width:430px}}
.chart{{margin-top:38px}}
.axis,.row{{display:grid;grid-template-columns:330px 1fr 92px;column-gap:28px}}
.scale{{position:relative;height:26px}}
.scale span{{position:absolute;transform:translateX(-50%);font-family:'Geist Mono';font-size:17px;color:var(--faint)}}
.rows{{position:relative;margin-top:6px}}
.gridwrap{{position:absolute;inset:0;display:grid;grid-template-columns:330px 1fr 92px;column-gap:28px;pointer-events:none}}
.gridwrap div{{position:relative;grid-column:2}}
.gridwrap i{{position:absolute;top:0;bottom:0;width:1px;background:var(--grid)}}
.row{{position:relative;align-items:center;height:{f["row"]}px}}
.m{{font-weight:600;font-size:26px;line-height:1.1;white-space:nowrap}}
.m em{{font-style:normal;color:var(--faint);font-weight:500}}
.k{{font-family:'Geist Mono';font-weight:500;font-size:15px;letter-spacing:.08em;color:var(--faint);margin-top:4px}}
.plot{{position:relative;height:100%}}
.rng{{position:absolute;top:50%;height:4px;margin-top:-2px;background:var(--dim);border-radius:2px}}
.dot{{position:absolute;top:50%;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:var(--volt);box-shadow:0 0 0 3px var(--pitch)}}
.v{{font-weight:700;font-size:26px;text-align:right;font-variant-numeric:tabular-nums}}
.key{{display:flex;gap:36px;margin-top:18px;font-size:20px;color:var(--stone);align-items:center}}
.key span{{display:flex;align-items:center;gap:12px}}
.key .kd{{width:16px;height:16px;border-radius:50%;background:var(--volt)}}
.key .kl{{width:44px;height:4px;border-radius:2px;background:var(--dim)}}
.foot{{margin-top:auto;border-top:1px solid var(--divider);padding-top:20px;font-family:'Geist Mono';font-size:17px;line-height:1.55;color:var(--label)}}
.foot .r2{{display:flex;justify-content:space-between;margin-top:10px;color:var(--stone)}}
</style></head><body><div class="card">
<div class="top"><img src="brand/xedge-logo-on-dark.svg" alt="xEdge"><div class="pill">18+</div></div>
<div class="label">MARGIN WATCH · {e(d["competition"].upper())} · <b>{e(date_span(rows))}</b></div>
<h1>The margin built into this weekend's prices</h1>
<div class="hero"><div class="num">{one_dp(d["overall_avg_pct"])}%</div>
<div class="cap">Average margin on the match result, across {len(rows)} matches and {d["bookmakers"]} UK bookmakers</div></div>
<div class="chart">
<div class="axis"><div></div><div class="scale">{tick_html}</div><div></div></div>
<div class="rows"><div class="gridwrap"><div>{grid_html}</div></div>{"".join(row_html)}</div>
<div class="key"><span><i class="kd"></i>Average across bookmakers</span><span><i class="kl"></i>Lowest to highest bookmaker</span></div>
</div>
<div class="foot">Prices at {e(d["captured_uk"])} from {d["bookmakers"]} UK-licensed bookmakers ({e(d["source"])}). Margin = home, draw and away implied chances added up, minus 100%. Prices may have changed.
<div class="r2"><span>18+ · Gambling help: National Gambling Helpline 0808 8020 133</span><span>xedge.live</span></div></div>
</div></body></html>"""


def render(d: dict, fmt: str, out_path: pathlib.Path) -> None:
    f = FORMATS[fmt]
    with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
        tmp.write(build_html(d, fmt))
        html_path = pathlib.Path(tmp.name)
    png_path = html_path.with_suffix(".png")
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": f["w"], "height": f["h"]}, device_scale_factor=2)
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)
            fonts_ok = page.evaluate("document.fonts.check(\"800 54px 'Archivo'\") && document.fonts.check(\"500 20px 'Geist Mono'\")")
            overflow = page.evaluate("(() => { const c = document.querySelector('.card'); return c.scrollHeight > c.clientHeight || c.scrollWidth > c.clientWidth; })()")
            page.screenshot(path=str(png_path))
            browser.close()
        if not fonts_ok:
            sys.exit("Fonts did not load")
        if overflow:
            sys.exit(f"Layout overflow in the {fmt} card")
        img = Image.open(png_path).convert("RGB").resize((f["w"], f["h"]), Image.LANCZOS)
        img.save(out_path, "JPEG", quality=92, optimize=True)
    finally:
        html_path.unlink(missing_ok=True)
        png_path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("figures", help="JSON file of figures (keep it outside this repo)")
    ap.add_argument("out_dir", help="output folder, normally cards/YYYY-MM-DD")
    a = ap.parse_args()
    d = json.loads(pathlib.Path(a.figures).read_text())
    problems = check(d)
    if problems:
        sys.exit("Refusing to render:\n- " + "\n- ".join(problems))
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for fmt in FORMATS:
        path = out_dir / f"margin-watch-{fmt}.jpg"
        render(d, fmt, path)
        paths[fmt] = str(path)
    print(json.dumps({"files": paths, "alt_text": alt_text(d)}, indent=2))


if __name__ == "__main__":
    main()

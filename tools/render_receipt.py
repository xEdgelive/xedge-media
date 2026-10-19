#!/usr/bin/env python3
"""Render an xEdge receipt card (1080x1350): an example bet shown as a receipt, with the
bookmaker's margin as a line item ("If bets came with a receipt, this line would be on it.").

Usage:
  python3 tools/render_receipt.py receipt.json cards/YYYY-MM-DD --name if-bets-came-with-a-receipt

Writes <name>.jpg into the output folder, then prints JSON with the file path, the alt text,
the figures it worked out and any wording warnings.

receipt.json (keep it outside this repo):
{
  "market": "Match result",
  "outcomes": [["Home", "11/10"], ["Draw", "12/5"], ["Away", "13/5"]],
  "pick": "Away",
  "pick_label": "away win",
  "stake": 10,
  "line": "Built into the price you see."
}
- "outcomes": every outcome of one market, 2 or 3 of them, each [name, price]; a price is
  fractional ("13/5") or decimal ("3.60"). They are always example prices, never a real match.
- "pick": the outcome the receipt is for. "pick_label" is how it reads after the market
  ("Match result: away win"); it defaults to the pick in lower case.
- "stake": whole pounds, 1 to 100.
- "line": optional small print under the margin line, 40 characters at most.

The tool works out every figure itself, so the card can't carry a sum done by hand: the
payout at the offered price, the fair price with the margin taken out by the power method
(the same maths as the free checker on xedge.live and render_video.py's checker scene), the
payout at that fair price, and the difference, which is the margin kept from the payout.
It refuses a margin outside 0.5% to 30%, a bookmaker's name, wording that is banned in any
context (the same lists render_carousel.py uses, imported from it so they never drift apart),
text that is too long, and an output file that already exists (a post may be using it).
Softer wording matches are printed as warnings for a person to check against the Rules tab.
Every card gets the 18+ badge, the full National Gambling Helpline line and xedge.live.
"""
import argparse
import html
import json
import os
import pathlib
import re
import sys
import tempfile
from fractions import Fraction

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_carousel import BANNED, BOOKMAKERS, WARN  # noqa: E402  (one source for the word lists)

# Set XEDGE_CHROMIUM to a Chromium binary when Playwright can't download its own.
CHROMIUM = os.environ.get("XEDGE_CHROMIUM") or None
ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 1080, 1350
HEADLINE = "If bets came with a receipt, [[this line]] would be on it."
RECEIPT_W, TOOTH, DEPTH = 760, 24, 14
LIMITS = {"market": 24, "outcome": 12, "pick_label": 20, "pick_row": 36, "line": 40}


def to_decimal(price: str) -> float:
    """'13/5' -> 3.6, '3.60' -> 3.6. Raises ValueError on anything else."""
    p = str(price).strip()
    if re.fullmatch(r"\d+/\d+", p):
        frac = Fraction(p)
        if frac <= 0:
            raise ValueError(p)
        return float(frac + 1)
    if re.fullmatch(r"\d+(\.\d+)?", p):
        return float(p)
    raise ValueError(p)


def power_fair_chances(prices: list) -> tuple:
    """Fair chances with the margin taken out by the power method: find k with sum(q_i^k) = 1."""
    q = [1 / x for x in prices]
    lo, hi = 0.5, 5.0
    for _ in range(200):
        k = (lo + hi) / 2
        if sum(x ** k for x in q) > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return k, [x ** k for x in q]


def pounds(x: float) -> str:
    return f"£{x:,.2f}"


def words_check(texts: list) -> tuple:
    problems, warnings = [], []
    blob = " ".join(texts).lower().replace("’", "'").replace("‘", "'")
    for name in BOOKMAKERS:
        if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", blob):
            problems.append(f"names a bookmaker ({name})")
    for pat in BANNED:
        if re.search(r"\b" + pat + r"\b", blob):
            problems.append(f"uses banned wording ({pat})")
    for pat in WARN:
        m = re.search(r"\b" + pat + r"\b", blob)
        if m:
            warnings.append(f"check the context of \"{m.group(0)}\" against the Rules tab")
    return problems, warnings


def work_out(d: dict) -> tuple:
    """Return (figures, problems, warnings) for a receipt.json dict."""
    problems = []
    market = str(d.get("market", "")).strip()
    outcomes = d.get("outcomes")
    pick = str(d.get("pick", "")).strip()
    pick_label = str(d.get("pick_label") or pick.lower()).strip()
    line = str(d.get("line", "")).strip()
    stake = d.get("stake")
    if not market or len(market) > LIMITS["market"]:
        problems.append(f"market must be 1 to {LIMITS['market']} characters")
    names, prices, shown = [], [], []
    if not isinstance(outcomes, list) or len(outcomes) not in (2, 3):
        problems.append("outcomes must list 2 or 3 [name, price] pairs")
        outcomes = []
    for o in outcomes:
        if not (isinstance(o, list) and len(o) == 2):
            problems.append("each outcome must be [name, price]")
            continue
        name, price = str(o[0]).strip(), str(o[1]).strip()
        if not name or len(name) > LIMITS["outcome"]:
            problems.append(f"outcome name {name!r} must be 1 to {LIMITS['outcome']} characters")
        try:
            dec = to_decimal(price)
        except ValueError:
            problems.append(f"can't read the price {price!r}")
            continue
        if not 1.01 <= dec <= 1000:
            problems.append(f"price {price} is out of range")
        names.append(name)
        prices.append(dec)
        shown.append(price)
    if len(set(n.lower() for n in names)) != len(names):
        problems.append("outcome names must differ")
    word_problems, warnings = words_check([market, pick_label, line] + names)
    problems += word_problems
    if len(line) > LIMITS["line"]:
        problems.append(f"line must be {LIMITS['line']} characters at most")
    if not isinstance(stake, int) or isinstance(stake, bool) or not 1 <= stake <= 100:
        problems.append("stake must be a whole number of pounds from 1 to 100")
        stake = 10
    if pick.lower() not in [n.lower() for n in names]:
        problems.append(f"pick {pick!r} isn't one of the outcomes")
    if problems and (len(prices) != len(outcomes) or pick.lower() not in [n.lower() for n in names]):
        return None, problems, warnings
    if not pick_label or len(pick_label) > LIMITS["pick_label"]:
        problems.append(f"pick_label must be 1 to {LIMITS['pick_label']} characters")
    if len(f"{market}: {pick_label}") > LIMITS["pick_row"]:
        problems.append(f"\"{market}: {pick_label}\" is too long for one line ({LIMITS['pick_row']} characters at most)")
    overround = sum(1 / x for x in prices)
    margin = overround - 1
    if not 0.005 <= margin <= 0.30:
        problems.append(f"the margin works out at {margin * 100:.2f}%, outside 0.5% to 30%; check the prices")
    k, fair = power_fair_chances(prices)
    i = [n.lower() for n in names].index(pick.lower())
    fair_price = 1 / fair[i]
    payout = round(stake * prices[i], 2)
    fair_payout = round(stake * fair_price, 2)
    kept = round(fair_payout - payout, 2)
    if kept <= 0:
        problems.append("the fair payout isn't above the offered payout; check the prices")
    figures = {
        "market": market, "pick_label": pick_label, "line": line, "stake": stake,
        "outcomes": list(zip(names, shown)), "pick_price_shown": shown[i], "pick_decimal": prices[i],
        "margin_pct": round(margin * 100, 2), "power_k": round(k, 5), "fair_price": round(fair_price, 3),
        "payout": payout, "fair_payout": fair_payout, "kept": kept,
    }
    return figures, problems, warnings


def price_text(shown: str, dec: float) -> str:
    return f"{shown} ({dec:.2f})" if "/" in shown else f"{dec:.2f}"


def example_note(f: dict) -> str:
    listed = ", ".join(f"{n.lower()} {p}" for n, p in f["outcomes"])
    return (f"Example prices: {listed}. Fair price {f['fair_price']:.3f}, with the margin taken out "
            f"by the power method, as in xEdge's free checker.")


def alt_text(f: dict) -> str:
    line = f", {f['line'][0].lower()}{f['line'][1:].rstrip('.')}" if f["line"] else ""
    listed = ", ".join(f"{n.lower()} {p}" for n, p in f["outcomes"])
    return (f"If bets came with a receipt, this line would be on it. An example receipt, not a real bet: "
            f"{f['market'].lower()}, {f['pick_label']}, price {price_text(f['pick_price_shown'], f['pick_decimal'])}, "
            f"stake {pounds(f['stake'])}. If it wins, you're paid {pounds(f['payout'])}. Paid at the fair price: "
            f"{pounds(f['fair_payout'])}. Kept as margin: {pounds(f['kept'])}{line}. Example prices: {listed}. "
            f"Fair price {f['fair_price']:.3f}, with the margin taken out by the power method. "
            f"18+. Gambling help: National Gambling Helpline 0808 8020 133.")


def zigzag(top: bool) -> str:
    pts = []
    for i, x in enumerate(range(0, RECEIPT_W + TOOTH // 2, TOOTH // 2)):
        y = (0 if i % 2 == 0 else DEPTH) if top else (DEPTH if i % 2 == 0 else 0)
        pts.append(f"{min(x, RECEIPT_W)},{y}")
    pts += [f"{RECEIPT_W},{DEPTH}", f"0,{DEPTH}"] if top else [f"{RECEIPT_W},0", "0,0"]
    return (f'<svg width="{RECEIPT_W}" height="{DEPTH}" viewBox="0 0 {RECEIPT_W} {DEPTH}" style="display:block">'
            f'<polygon points="{" ".join(pts)}" fill="#F3F5EF"/></svg>')


def rows(items: list) -> str:
    e = html.escape
    out = []
    for left, right in items:
        lead = '<span class="lead"></span>' if right else ""
        out.append(f'<div class="row"><span>{e(left)}</span>{lead}<span>{e(right)}</span></div>')
    return "".join(out)


def card_html(f: dict) -> str:
    e = html.escape
    headline = re.sub(r"\[\[(.+?)\]\]", r'<span class="hl">\1</span>', e(HEADLINE))
    first = [(f"{f['market']}: {f['pick_label']}", ""),
             ("Price", price_text(f["pick_price_shown"], f["pick_decimal"])),
             ("Stake", pounds(f["stake"]))]
    second = [("If it wins, you're paid", pounds(f["payout"])),
              ("Paid at the fair price", pounds(f["fair_payout"]))]
    why = f'<div class="why">{e(f["line"])}</div>' if f["line"] else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Archivo';src:url('fonts/archivo-variable.woff2') format('woff2-variations');font-weight:100 900;font-stretch:62% 125%}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-400.woff2') format('woff2');font-weight:400}}
@font-face{{font-family:'Geist Mono';src:url('fonts/geist-mono-500.woff2') format('woff2');font-weight:500}}
:root{{--pitch:#0C0E0D;--volt:#C8F53A;--chalk:#F3F5EF;--stone:#A3A8A1;--label:#8A8F88;--pill:#343936;--divider:#232826;--ink:#0C0E0D;--inkfaint:#5B615C}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;background:var(--pitch)}}
body{{font-family:'Archivo',sans-serif;color:var(--chalk);-webkit-font-smoothing:antialiased}}
.card{{width:{W}px;height:{H}px;padding:64px 72px 56px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;height:48px}}
.top img{{height:40px;display:block}}
.pill{{font-family:'Geist Mono';font-weight:500;font-size:20px;letter-spacing:.08em;color:var(--stone);border:2px solid var(--pill);border-radius:999px;padding:7px 16px 6px}}
.main{{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;padding:36px 0 28px}}
h1{{font-weight:800;font-stretch:125%;line-height:1.04;letter-spacing:-.01em;font-size:66px}}
.hl{{color:var(--volt)}}
.paperwrap{{margin-top:52px;align-self:center;transform:rotate(-1.6deg);filter:drop-shadow(0 28px 40px rgba(0,0,0,.55))}}
.paper{{width:{RECEIPT_W}px;background:var(--chalk);color:var(--ink);font-family:'Geist Mono';font-weight:500;padding:30px 46px 34px}}
.head{{text-align:center;font-size:34px;letter-spacing:.32em;padding-left:.32em}}
.sub{{text-align:center;font-size:18px;letter-spacing:.14em;color:var(--inkfaint);margin-top:10px}}
.rule{{border-top:3px dashed rgba(12,14,13,.35);margin:24px 0}}
.row{{display:flex;align-items:baseline;gap:14px;font-size:28px;line-height:1.25;padding:7px 0;white-space:nowrap}}
.lead{{flex:1;border-bottom:3px dotted rgba(12,14,13,.3);transform:translateY(-7px)}}
.kept{{display:flex;align-items:baseline;gap:14px;background:var(--volt);margin:0 -22px;padding:16px 22px;font-size:32px;white-space:nowrap}}
.kept .lead{{border-color:rgba(12,14,13,.45)}}
.why{{font-size:20px;color:var(--inkfaint);text-align:center;margin-top:18px;letter-spacing:.04em}}
.bars{{height:44px;margin:26px auto 0;width:420px;background:repeating-linear-gradient(90deg,var(--ink) 0 3px,transparent 3px 7px,var(--ink) 7px 8px,transparent 8px 13px,var(--ink) 13px 17px,transparent 17px 20px);opacity:.85}}
.note{{font-family:'Geist Mono';font-size:19px;line-height:1.5;color:var(--label);margin-bottom:18px}}
.foot{{border-top:1px solid var(--divider);padding-top:20px;display:flex;justify-content:space-between;font-family:'Geist Mono';font-size:19px;color:var(--stone)}}
.foot .site{{color:var(--label)}}
</style></head><body><div class="card">
<div class="top"><img src="brand/xedge-logo-on-dark.svg" alt="xEdge"><div class="pill">18+</div></div>
<div class="main">
<h1>{headline}</h1>
<div class="paperwrap">{zigzag(True)}<div class="paper">
<div class="head">RECEIPT</div>
<div class="sub">EXAMPLE · NOT A REAL BET</div>
<div class="rule"></div>
{rows(first)}
<div class="rule"></div>
{rows(second)}
<div class="rule"></div>
<div class="kept"><span>KEPT AS MARGIN</span><span class="lead"></span><span>{e(pounds(f["kept"]))}</span></div>
{why}
<div class="bars"></div>
</div>{zigzag(False)}</div>
</div>
<div class="note">{e(example_note(f))}</div>
<div class="foot"><span>18+ · Gambling help: National Gambling Helpline 0808 8020 133</span><span class="site">xedge.live</span></div>
</div></body></html>"""


FIT_JS = """() => {
  const card = document.querySelector('.card').getBoundingClientRect();
  const main = document.querySelector('.main');
  const paper = document.querySelector('.paper');
  const wide = [...paper.querySelectorAll('.row, .kept')].some(el => el.scrollWidth > el.clientWidth + 1);
  const outside = [...document.querySelectorAll('.card *')].some(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && (r.bottom > card.bottom + 1 || r.right > card.right + 1 || r.left < card.left - 1);
  });
  return {tall: main.scrollHeight > main.clientHeight + 1, wide: wide || outside};
}"""


def render(f: dict, out_path: pathlib.Path) -> None:
    with tempfile.NamedTemporaryFile("w", prefix=".render-", suffix=".html", dir=ROOT, delete=False) as tmp:
        tmp.write(card_html(f))
        html_path = pathlib.Path(tmp.name)
    png_path = html_path.with_suffix(".png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            if not page.evaluate("document.fonts.check(\"800 66px 'Archivo'\") && document.fonts.check(\"500 20px 'Geist Mono'\")"):
                sys.exit("Fonts did not load")
            fit = page.evaluate(FIT_JS)
            if fit["tall"] or fit["wide"]:
                sys.exit("The receipt doesn't fit the card; shorten the market, pick_label or line")
            page.screenshot(path=str(png_path))
            browser.close()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.open(png_path).convert("RGB").resize((W, H), Image.LANCZOS).save(out_path, "JPEG", quality=92, optimize=True)
    finally:
        html_path.unlink(missing_ok=True)
        png_path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render an xEdge receipt card.")
    ap.add_argument("receipt_json")
    ap.add_argument("out_dir", help="for example cards/2026-10-26")
    ap.add_argument("--name", required=True, help="lowercase words and hyphens, 48 characters at most")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name) or len(a.name) > 48:
        sys.exit("--name must be lowercase words joined by hyphens, 48 characters at most")
    out_dir = pathlib.Path(a.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_path = out_dir / f"{a.name}.jpg"
    shown_path = str(out_path.relative_to(ROOT)) if out_path.is_relative_to(ROOT) else str(out_path)
    if out_path.exists():
        sys.exit(f"{shown_path} already exists; a post may be using it, so pick a new name")
    try:
        d = json.loads(pathlib.Path(a.receipt_json).read_text())
    except (OSError, json.JSONDecodeError) as err:
        sys.exit(f"Can't read {a.receipt_json}: {err}")
    figures, problems, warnings = work_out(d if isinstance(d, dict) else {})
    if problems:
        sys.exit("Refused:\n- " + "\n- ".join(problems))
    render(figures, out_path)
    print(json.dumps({"file": shown_path, "alt_text": alt_text(figures),
                      "figures": figures, "warnings": warnings}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check the text of social posts against xEdge's wording rules before they go to Buffer.

Usage:
    python3 tools/check_post_text.py posts.json

posts.json is a list of posts, each {"id": "...", "channel": "x" | "instagram" | "facebook" |
"tiktok", "text": "...", "needs_18": true or false}. Put each post of a thread in as its own
entry. For every post it prints one line of JSON with its problems and warnings, and it exits
with status 1 if any post has a problem.

Problems, which stop a post going out as written:
- a bookmaker's or exchange's name, or wording that is banned in any context (the same lists
  render_carousel.py uses for the cards, read from that file so they never drift apart);
- the helpline number or an AI label in the text (left out of captions since 13 Oct 2026; the
  helpline stays on the cards, the video frames and the bios);
- a square bracket, which usually means a [placeholder] was never filled in;
- no "18+" where needs_18 is true, an empty text, or more characters than the channel allows
  (280 on X, 2,200 on Instagram and TikTok).

Warnings are words that are fine in context, such as "guaranteed" used to warn readers off a
claim, or xEdge "locking" a selection before kickoff. A person, or the routine, judges each one.

Standard library only, so it runs before the render tools are installed.
"""
import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
LIMITS = {"x": 280, "instagram": 2200, "tiktok": 2200, "facebook": 63206}
TEXT_RULES = [
    (r"0808|gambling help|national gambling helpline|gamcare|begambleaware",
     "gives the helpline, which captions leave out since 13 Oct 2026"),
    (r"\bai[- ]?(voice ?-?over|generated|made)\b|\bmade (with|by) ai\b|#ai\b",
     "carries an AI label, which posts go without since 13 Oct 2026"),
    (r"[\[\]]", "has a square bracket, so a placeholder may be left to fill"),
]


def word_lists() -> tuple:
    tree = ast.parse((HERE / "render_carousel.py").read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("BOOKMAKERS", "BANNED", "WARN")):
            found[node.targets[0].id] = ast.literal_eval(node.value)
    missing = {"BOOKMAKERS", "BANNED", "WARN"} - set(found)
    if missing:
        sys.exit(f"render_carousel.py has no {', '.join(sorted(missing))} list.")
    return found["BOOKMAKERS"], found["BANNED"], found["WARN"]


def check(post: dict, bookmakers: list, banned: list, warn: list) -> tuple:
    problems, warnings = [], []
    text = str(post.get("text", ""))
    channel = post.get("channel")
    if channel not in LIMITS:
        problems.append(f"unknown channel {channel!r}")
    elif len(text) > LIMITS[channel]:
        problems.append(f"{len(text)} characters, over the {LIMITS[channel]} allowed on {channel}")
    if not text.strip():
        problems.append("the text is empty")
    if post.get("needs_18") and "18+" not in text:
        problems.append("doesn't say 18+")
    low = text.lower().replace("’", "'").replace("‘", "'")
    for name in bookmakers:
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", low):
            problems.append(f"names a bookmaker ({name})")
    for pattern in banned:
        m = re.search(rf"\b{pattern}\b", low)
        if m:
            problems.append(f"banned wording ({m.group(0)!r})")
    for pattern, why in TEXT_RULES:
        if re.search(pattern, low):
            problems.append(why)
    for pattern in warn:
        m = re.search(rf"\b{pattern}\b", low)
        if m:
            warnings.append(f"check the context of {m.group(0)!r}")
    return problems, warnings


def main(argv: list) -> None:
    if len(argv) != 2:
        sys.exit(__doc__)
    posts = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        sys.exit("posts.json must be a list of posts.")
    bookmakers, banned, warn = word_lists()
    failed = False
    for post in posts:
        problems, warnings = check(post, bookmakers, banned, warn)
        failed = failed or bool(problems)
        print(json.dumps({"id": post.get("id"), "problems": problems, "warnings": warnings},
                         ensure_ascii=False))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(sys.argv)

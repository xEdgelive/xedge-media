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
  (2,200 on Instagram and TikTok; 280 on X, counted X's way: every link as 23 characters and
  most characters outside Latin, Greek and Cyrillic, emoji included, as 2).

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
    (r"0808|gambling help|national gambling helpline|gamcare|gambleaware",
     "gives the helpline, which captions leave out since 13 Oct 2026"),
    (r"\bai[- ]?(voice|voiced|voice ?-?over|narrat\w*|generated|made|created)\b"
     r"|\b(voiced|narrated|made|created|generated|written) (by|with|using) ai\b"
     r"|#ai\b|\bai label\b|\bsynthetic voice\b",
     "carries an AI label, which posts go without since 13 Oct 2026"),
    (r"[\[\]]", "has a square bracket, so a placeholder may be left to fill"),
]


URL = re.compile(r"(?i)\b(?:https?://\S+|(?:[a-z0-9-]+\.)+(?:com|co\.uk|uk|org|net|io|app|live|dev|ai|me|tv)\b(?:/\S*)?)")


def weigh(text: str) -> int:
    """Characters as X counts them: 1 for Latin, Greek, Cyrillic and common punctuation, 2 otherwise."""
    n = 0
    for ch in text:
        cp = ord(ch)
        n += 1 if cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247 else 2
    return n


def x_length(text: str) -> int:
    """A post's length on X: every link counts as 23 characters, whatever its real length."""
    total, pos = 0, 0
    for m in URL.finditer(text):
        total += weigh(text[pos:m.start()]) + 23
        pos = m.end()
    return total + weigh(text[pos:])


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
    length = x_length(text) if channel == "x" else len(text)
    if channel not in LIMITS:
        problems.append(f"unknown channel {channel!r}")
    elif length > LIMITS[channel]:
        problems.append(f"{length} characters, over the {LIMITS[channel]} allowed on {channel}")
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

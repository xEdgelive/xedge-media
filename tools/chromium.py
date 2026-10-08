"""Launch headless Chromium for the renderers, in this order:

1. XEDGE_CHROMIUM, a Chrome or chrome-headless-shell binary, if it is set.
2. Playwright's own browser (python3 -m playwright install chromium).
3. The newest Chromium already on the machine: another Playwright version's browser (in
   PLAYWRIGHT_BROWSERS_PATH, ~/.cache/ms-playwright or /opt/pw-browsers) or Chrome for Testing
   fetched into ~/browsers with npx @puppeteer/browsers. Cloud environments that block browser
   downloads usually come with one of these.
"""
import os
import pathlib
import re
import sys

# Playwright's headless shell (old and new folder layouts) first, then its full Chromium.
PATTERNS = (("chromium_headless_shell-*/chrome-*/headless_shell", "chromium_headless_shell-*/chrome-*/chrome-headless-shell"),
            ("chromium-*/chrome-*/chrome",))


def _version(path: pathlib.Path, base: pathlib.Path) -> list:
    """The version in the first folder below base: a Playwright revision (1194) or a Chrome version (141.0.7390.54)."""
    return [int(n) for n in re.findall(r"\d+", path.relative_to(base).parts[0])]


def installed() -> list:
    """Chromium binaries already on this machine, newest first within each place."""
    found = []
    for root in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "~/.cache/ms-playwright", "/opt/pw-browsers"):
        if root:
            base = pathlib.Path(root).expanduser()
            for group in PATTERNS:
                matches = [p for pattern in group for p in base.glob(pattern)]
                found += sorted(matches, key=lambda p: _version(p, base), reverse=True)
    puppeteer = pathlib.Path("~/browsers/chrome-headless-shell").expanduser()
    found += sorted(puppeteer.glob("*/*/chrome-headless-shell"), key=lambda p: _version(p, puppeteer), reverse=True)
    return [p for p in dict.fromkeys(found) if p.is_file() and os.access(p, os.X_OK)]


def launch(p):
    """A headless Chromium browser from Playwright instance p."""
    chosen = os.environ.get("XEDGE_CHROMIUM")
    if chosen:
        if not os.access(chosen, os.X_OK):
            sys.exit(f"XEDGE_CHROMIUM is set to {chosen}, which isn't an executable file")
        return p.chromium.launch(executable_path=chosen)
    try:
        return p.chromium.launch()
    except Exception as e:
        if "Executable doesn't exist" not in str(e):
            raise
    tried = []
    for exe in installed():
        try:
            browser = p.chromium.launch(executable_path=str(exe))
        except Exception as e:
            tried.append(f"{exe}: {str(e).splitlines()[0]}")
            continue
        print(f"Playwright's own browser isn't installed; using {exe}", file=sys.stderr)
        return browser
    sys.exit("No Chromium that works: run python3 -m playwright install chromium, or set XEDGE_CHROMIUM to a Chrome "
             "or chrome-headless-shell binary" + "".join(f"\n- tried {t}" for t in tried))

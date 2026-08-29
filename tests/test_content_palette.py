"""Regression test for the marble reading-area palette on the AWA Archiwum
public site (prompt-archiwum-marmurowa-paleta-tresci.md).

The article body (.art-body -- #articleBody and #pageBody) gets its own
fixed, marble-inspired background/ink/line palette (--content-bg/-ink/
-muted/-line, defined once on bare :root, not inside
:root[data-theme="light"]) that must stay IDENTICAL regardless of the
site's own dark/light toggle -- the same "reading pane doesn't follow the
shell's theme" idea AWA Czytnik already uses for its book view. Everything
OUTSIDE .art-body (nav, topbar) must keep reacting to the toggle normally;
this test checks both halves of that claim, not just the "stays fixed"
half, so a toggle that silently stopped doing anything at all couldn't
accidentally pass it.

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py / test_print_pdf.py (fetch() rejected under
file://, must never touch the real archiwum-public/data/ folder).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_content_palette.py
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
import http.server
import functools
import json
import re
import shutil
import sys
import io
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
errors = []


def check(label, cond):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        errors.append(label)


def rel_lum(rgb):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(rgb1, rgb2):
    l1, l2 = rel_lum(rgb1), rel_lum(rgb2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def parse_rgb(s):
    return tuple(float(x) for x in re.findall(r"[\d.]+", s)[:3])


WCAG_AA_TEXT = 4.5

FIXTURE = {
    "articles": {"articles": [
        {"id": "art1", "title": "Artykul Testowy", "signature": "AWA/2026/001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": ("<h2>Naglowek w tresci</h2>"
                      "<p>Zwykly akapit tekstu.</p>"
                      "<blockquote>Cytat blokowy zrodlowy.</blockquote>"
                      "<p><sup>1</sup> odnosnik do przypisu.</p>"),
         "bodyText": "", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None, "status": "published"},
    ]},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": []},
    "persons": {"persons": []},
    "relations": {"relations": []},
    "epochs": {"epochs": []},
    "pages": {"pages": []},
}

site_dir = HERE / "_test_content_palette_site"
if site_dir.exists():
    shutil.rmtree(site_dir)
(site_dir / "data").mkdir(parents=True)
shutil.copy(REPO / "index.html", site_dir / "index.html")
if (REPO / "assets").exists():
    shutil.copytree(REPO / "assets", site_dir / "assets")
for name, payload in FIXTURE.items():
    (site_dir / "data" / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))

        page.goto(f"http://127.0.0.1:{port}/index.html?article=art1")
        page.wait_for_function("() => ARTICLES.length > 0")
        page.wait_for_timeout(200)

        check("default theme is dark (no data-theme attribute)",
              page.evaluate("() => document.documentElement.getAttribute('data-theme')") is None)

        def measure():
            return {
                "bg": page.evaluate("() => getComputedStyle(document.getElementById('articleBody')).backgroundColor"),
                "heading_ink": page.evaluate("() => getComputedStyle(document.querySelector('#articleBody h2')).color"),
                "p_ink": page.evaluate("() => getComputedStyle(document.querySelector('#articleBody p')).color"),
                "bq_border": page.evaluate("() => getComputedStyle(document.querySelector('#articleBody blockquote')).borderLeftColor"),
                "bq_ink": page.evaluate("() => getComputedStyle(document.querySelector('#articleBody blockquote')).color"),
                "sup_ink": page.evaluate("() => getComputedStyle(document.querySelector('#articleBody sup')).color"),
            }

        marble_dark = measure()
        nav_bg_dark = page.evaluate("() => getComputedStyle(document.getElementById('nav')).backgroundImage")

        page.click("#themeToggleBtn")
        page.wait_for_timeout(150)
        check("data-theme becomes 'light' after clicking the toggle",
              page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light")

        marble_light = measure()
        nav_bg_light = page.evaluate("() => getComputedStyle(document.getElementById('nav')).backgroundImage")

        check("sanity check: #nav background DOES change with the toggle "
              "(proves the marble palette below is a deliberate exception, not a broken/no-op toggle)",
              nav_bg_dark != nav_bg_light)

        for key in marble_dark:
            check(f".art-body '{key}' is identical in dark vs light mode ({marble_dark[key]!r})",
                  marble_dark[key] == marble_light[key])

        check(".art-body background is not just the page background showing through",
              "rgba(0, 0, 0, 0)" not in marble_dark["bg"] and marble_dark["bg"] != "transparent")

        art_bg = parse_rgb(marble_dark["bg"])
        for key in ("heading_ink", "p_ink"):
            ratio = contrast(parse_rgb(marble_dark[key]), art_bg)
            check(f".art-body '{key}' vs marble background clears {WCAG_AA_TEXT}:1 AA (measured {ratio:.2f}:1)",
                  ratio >= WCAG_AA_TEXT)
        bq_ratio = contrast(parse_rgb(marble_dark["bq_ink"]), art_bg)
        check(f".art-body blockquote text vs marble background clears {WCAG_AA_TEXT}:1 AA (measured {bq_ratio:.2f}:1)",
              bq_ratio >= WCAG_AA_TEXT)

        # ---------- .art-body on the OTHER real container sharing the class (#pageBody) ----------
        page.evaluate("""() => {
            document.querySelectorAll('.module').forEach(m=>m.classList.toggle('active', m.id==='mod-page'));
            document.getElementById('pageTitle').textContent = 'Strona testowa';
            document.getElementById('pageBody').innerHTML = '<p>Tresc strony.</p>';
        }""")
        page.wait_for_timeout(100)
        page_body_bg = page.evaluate("() => getComputedStyle(document.getElementById('pageBody')).backgroundColor")
        check("#pageBody (the OTHER .art-body container, used for self-service Strony) gets the same marble background",
              page_body_bg == marble_dark["bg"])

        check("no console/page errors across the whole test", len(errors) == 0)
        browser.close()
finally:
    shutil.rmtree(site_dir, ignore_errors=True)
    httpd.shutdown()

print()
if errors:
    print(f"{len(errors)} FAILURE(S):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("CONTENT PALETTE (MARBLE READING AREA) TEST PASSED")

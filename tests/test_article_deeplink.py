"""Regression test for per-article deep links (?article=<id>) on the AWA
Archiwum public site (archiwum-public/index.html).

Added alongside the RSS feed feature: an RSS <item>'s <link> has to
actually open the right article on a fresh page load, which the site could
not do before -- openArticle() only mutated in-page DOM state, never the
URL, so there was no article-specific URL to put in a feed at all. See the
admin panel's articleFeedLink() (awa-archiwum-admin.html) for the exact URL
shape this test's fixture link needs to match: SITE_URL + '?article=' + id.

Same isolated-temp-site + local http.server pattern as
test_article_status.py (fetch() of local files is rejected under file://,
and this must never touch the real archiwum-public/data/ folder) -- see
that file's docstring for why.

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_article_deeplink.py
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
import http.server
import functools
import json
import shutil
import sys
import io
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
errors = []

FIXTURE = {
    "articles": {"articles": [
        {"id": "art_a", "title": "Artykul A", "signature": "A-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Tresc A.</p>", "bodyText": "Tresc A.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None, "status": "published"},
        {"id": "art_b", "title": "Artykul B", "signature": "B-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Tresc B.</p>", "bodyText": "Tresc B.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-02T00:00:00.000Z", "pdfBase64": None, "status": "published"},
        {"id": "art_draft", "title": "Artykul Roboczy", "signature": "D-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Roboczy.</p>", "bodyText": "Roboczy.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-03T00:00:00.000Z", "pdfBase64": None, "status": "draft"},
    ]},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": []},
    "persons": {"persons": []},
    "relations": {"relations": []},
}

site_dir = HERE / "_test_deeplink_site"
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
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))

        # --- TEST 1: fresh load with ?article=<id> opens that article directly ---
        page.goto(f"http://127.0.0.1:{port}/index.html?article=art_b")
        page.wait_for_function("() => ARTICLES.length > 0")
        assert "mod-article" in (page.locator(".module.active").get_attribute("id") or ""), \
            "a fresh load with ?article=art_b should land directly on the article view"
        assert page.locator("#articleTitle").inner_text() == "Artykul B"
        print("TEST 1 (fresh load with ?article=<id> opens that article directly) OK")

        # --- TEST 2: ?article=<unknown id> falls back to the dashboard, not a blank/broken view ---
        page.goto(f"http://127.0.0.1:{port}/index.html?article=does-not-exist")
        page.wait_for_function("() => ARTICLES.length > 0")
        assert "mod-start" in (page.locator(".module.active").get_attribute("id") or ""), \
            "an unknown ?article= id should fall back to the start module, not stay stuck"
        print("TEST 2 (unknown ?article= id falls back to dashboard) OK")

        # --- TEST 3: ?article= for a DRAFT article (not in the fetched ARTICLES array at all,
        # filtered out by loadAllData() the same as everywhere else) also falls back, doesn't crash ---
        page.goto(f"http://127.0.0.1:{port}/index.html?article=art_draft")
        page.wait_for_function("() => ARTICLES.length > 0")
        assert "mod-start" in (page.locator(".module.active").get_attribute("id") or ""), \
            "a ?article= id pointing at a draft article must not open it (same filter as everywhere else)"
        print("TEST 3 (?article= pointing at a draft falls back, draft never exposed via URL) OK")

        # --- TEST 4: openArticle() pushes a real, shareable URL; switching to another
        # nav module clears it again (URL must not keep lying about what's shown) ---
        page.goto(f"http://127.0.0.1:{port}/index.html")
        page.wait_for_function("() => ARTICLES.length > 0")
        page.evaluate("() => openArticle('art_a')")
        page.wait_for_timeout(150)
        assert "article=art_a" in page.evaluate("() => location.search")
        page.evaluate("() => switchModule('browse')")
        page.wait_for_timeout(150)
        assert page.evaluate("() => location.search") == "", \
            "navigating to another module must clear the stale ?article= param"
        print("TEST 4 (openArticle pushes a real URL; switching modules clears it) OK")

        # --- TEST 5: browser back button (popstate) re-opens the article whose URL it returns to ---
        page.goto(f"http://127.0.0.1:{port}/index.html")
        page.wait_for_function("() => ARTICLES.length > 0")
        page.evaluate("() => openArticle('art_a')")
        page.wait_for_timeout(150)
        page.evaluate("() => openArticle('art_b')")
        page.wait_for_timeout(150)
        page.go_back()
        page.wait_for_timeout(200)
        assert "article=art_a" in page.evaluate("() => location.search")
        assert page.locator("#articleTitle").inner_text() == "Artykul A", \
            "clicking back should re-render the article the URL went back to, not just change the URL"
        print("TEST 5 (browser back button re-opens the previous article via popstate) OK")

        browser.close()
finally:
    httpd.shutdown()
    shutil.rmtree(site_dir, ignore_errors=True)

print("--- CONSOLE / PAGE ERRORS ---")
if errors:
    for e in errors:
        print(e)
    sys.exit(1)
print("(none)")
print("\nARTICLE DEEP-LINK TEST PASSED")

"""Regression test for article draft/published status on the AWA Archiwum
public site (archiwum-public/index.html).

fetch() of local files is rejected outright under file:// (Chromium's fetch()
implementation disallows the file: scheme at the API level, before any
request even reaches the network layer Playwright's page.route() intercepts
-- confirmed empirically, route() never fires for these requests). CLAUDE.md
already documents the real fix: serve the page over a local HTTP server. This
test does that against an ISOLATED TEMP COPY of index.html with its own
fixture data/*.json -- never the real archiwum-public/data/ folder, which may
carry real, not-yet-published/committed content that must not be touched or
overwritten by a test run.

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_article_status.py
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
    "articles": {
        "articles": [
            {"id": "art_definicja", "title": "DEFINICJA", "signature": "DEF-001", "category": "Podstawy",
             "conceptIds": ["concept_apostazja"], "personIds": [], "author": "", "sourceProject": "",
             "bodyHtml": "<p>Definicja.</p>", "bodyText": "Definicja tresc.", "footnotesHtml": "", "biblioHtml": "",
             "biblioItems": ["Zrodlo A"], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None},
            # legacy article: NO status field at all -> must be treated as published
            {"id": "art_legacy", "title": "Artykul Sprzed Zmiany", "signature": "LEG-001", "category": "Podstawy",
             "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
             "bodyHtml": "<p>Tresc.</p>", "bodyText": "tresc legacy", "footnotesHtml": "", "biblioHtml": "",
             "biblioItems": [], "importedAt": "2026-01-02T00:00:00.000Z", "pdfBase64": None},
            {"id": "art_draft", "title": "Artykul Roboczy", "signature": "DRAFT-001", "category": "Testy",
             "conceptIds": ["concept_apostazja"], "personIds": [], "author": "", "sourceProject": "",
             "bodyHtml": "<p>Roboczy.</p>", "bodyText": "tresc robocza szukaj-mnie", "footnotesHtml": "", "biblioHtml": "",
             "biblioItems": ["Zrodlo Robocze"], "importedAt": "2026-01-03T00:00:00.000Z", "pdfBase64": None,
             "status": "draft"},
            {"id": "art_published", "title": "Artykul Opublikowany", "signature": "PUB-001", "category": "Testy",
             "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
             "bodyHtml": "<p>Opublikowany.</p>", "bodyText": "tresc opublikowana", "footnotesHtml": "", "biblioHtml": "",
             "biblioItems": [], "importedAt": "2026-01-04T00:00:00.000Z", "pdfBase64": None,
             "status": "published"},
        ]
    },
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": [
        {"id": "concept_apostazja", "name": "Apostazja", "parentId": None, "description": ""},
        {"id": "concept_grzech", "name": "Grzech", "parentId": None, "description": ""},
    ]},
    "persons": {"persons": []},
    "relations": {"relations": [
        # documented ONLY by a draft article -> must be hidden entirely
        {"id": "rel_draft_only", "fromType": "concept", "fromId": "concept_apostazja", "toType": "concept",
         "toId": "concept_apostazja", "label": "tylko-robocza-relacja", "articleIds": ["art_draft"]},
        # documented by ONE draft + ONE published article -> relation itself
        # must stay visible (it has a published source), but clicking its
        # label to see source articles must show only the published one
        {"id": "rel_mixed", "fromType": "concept", "fromId": "concept_apostazja", "toType": "concept",
         "toId": "concept_grzech", "label": "mieszana-relacja", "articleIds": ["art_draft", "art_published"]},
    ]},
    "epochs": {"epochs": []},
}

# --- isolated temp site: copy of index.html + fixture data, never the real data/ folder ---
site_dir = HERE / "_test_site"
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
        page.goto(f"http://127.0.0.1:{port}/index.html")
        page.wait_for_timeout(300)

        # --- Krok 1: migracja - legacy artykul bez pola status = widoczny (DEFINICJA scenario) ---
        ids_loaded = page.evaluate("() => ARTICLES.map(a => a.id)")
        assert "art_legacy" in ids_loaded, ids_loaded
        assert "art_definicja" in ids_loaded, ids_loaded
        assert "art_published" in ids_loaded, ids_loaded
        assert "art_draft" not in ids_loaded, "draft article leaked into the global ARTICLES array"

        # --- Krok 3: kazde miejsce z Kroku 0 respektuje status ---
        page.evaluate("() => switchModule('start')")
        start_text = page.locator("#recentList").inner_text()
        assert "Artykul Roboczy" not in start_text, start_text
        assert "DEFINICJA" in start_text, start_text
        assert "Artykul Sprzed Zmiany" in start_text, start_text

        page.evaluate("() => switchModule('browse')")
        browse_text = page.locator("#browseList").inner_text()
        assert "Artykul Roboczy" not in browse_text, browse_text
        assert "DEFINICJA" in browse_text, browse_text

        page.evaluate("() => switchModule('search')")
        page.fill("#searchInput", "szukaj-mnie")  # word unique to the draft article's body text
        page.wait_for_timeout(150)
        search_text = page.locator("#searchResults").inner_text()
        assert "Artykul Roboczy" not in search_text, search_text

        page.evaluate("() => switchModule('sources')")
        sources_text = page.locator("#sourcesList").inner_text()
        assert "Zrodlo Robocze" not in sources_text, "a bibliography source cited only by a draft article must not appear"

        # --- Krok 0/3: Mapa Pojec - relacja dokumentowana wylacznie przez artykul roboczy znika calkowicie,
        # relacja z MIESZANYM zestawem artykulow (jeden roboczy + jeden opublikowany) zostaje widoczna
        # (ma >=1 opublikowane zrodlo), ale jej lista zrodel po kliknieciu pokazuje TYLKO opublikowany ---
        page.evaluate("() => switchModule('graph')")
        page.click(".graph-tab[data-tab='concepts']")
        page.wait_for_timeout(150)
        page.click(".az-term:has-text('Apostazja')")
        page.wait_for_timeout(150)
        graph_text = page.locator("#graphFocus").inner_text()
        assert "tylko-robocza-relacja" not in graph_text, graph_text
        assert "mieszana-relacja" in graph_text, graph_text

        page.click("[data-rel-articles='rel_mixed']")
        page.wait_for_timeout(150)
        rel_articles_text = page.locator("#graphRelationArticles").inner_text()
        assert "Artykul Opublikowany" in rel_articles_text, rel_articles_text
        assert "Artykul Roboczy" not in rel_articles_text, rel_articles_text

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
print("\nARTICLE STATUS (PUBLIC SITE) TEST PASSED")

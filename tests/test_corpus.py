"""Regression test for article corpora integrated into Mapa Pojec, on the
AWA Archiwum public site (prompt-archiwum-korpusy.md) -- same feature as
the admin panel's test_corpus.py, this time verifying the status filter:
only status==='published' articles may ever appear in "Artykuly z tym
haslem" or the corpus roll-up here, since ARTICLES on this site is already
filtered at load time (see loadAllData()) and the graph code itself
contains no status check of its own -- reusing that code correctly hides
drafts here with nothing extra written, the same principle already proven
for relations/showRelationArticles.

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py (fetch() of local files is rejected under
file://, and this must never touch the real archiwum-public/data/
folder).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_corpus.py
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


def check(label, cond):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        errors.append(label)


FIXTURE = {
    "articles": {"articles": [
        {"id": "art_deep", "title": "Artykul Gleboko Otagowany", "signature": "D-001", "category": "Testy",
         "conceptIds": ["c_indyferentyzm"], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Tresc.</p>", "bodyText": "Tresc.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None,
         "status": "published", "corpusId": "c_mysterium"},
        {"id": "art_shallow", "title": "Artykul Tylko Korpus", "signature": "S-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Tresc.</p>", "bodyText": "Tresc.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-02T00:00:00.000Z", "pdfBase64": None,
         "status": "published", "corpusId": "c_mysterium"},
        # DRAFT, tagged with the same corpus AND the same concept as art_deep --
        # must never appear anywhere on the public site.
        {"id": "art_draft_tagged", "title": "Artykul Roboczy Otagowany", "signature": "R-001", "category": "Testy",
         "conceptIds": ["c_indyferentyzm"], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Tresc.</p>", "bodyText": "Tresc.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-03T00:00:00.000Z", "pdfBase64": None,
         "status": "draft", "corpusId": "c_mysterium"},
    ]},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": [
        {"id": "c_mysterium", "name": "Mysterium Iniquitatis", "parentId": None, "description": ""},
        {"id": "c_synkretyzm", "name": "Synkretyzm", "parentId": "c_mysterium", "description": ""},
        {"id": "c_indyferentyzm", "name": "Indyferentyzm", "parentId": "c_synkretyzm", "description": ""},
    ]},
    "persons": {"persons": []},
    "relations": {"relations": []},
}

site_dir = HERE / "_test_corpus_site"
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
        page.wait_for_function("() => ARTICLES.length > 0")

        page.click('[data-mod="graph"]')
        page.wait_for_timeout(200)

        # ---------- non-root node: "Artykuly z tym haslem" ----------
        page.click("#graphIndexConcepts .az-term:has-text('Indyferentyzm')")
        page.wait_for_timeout(200)
        focus_text = page.locator("#graphFocus").inner_text()
        check("published article tagged with this concept appears under it",
              "Artykul Gleboko Otagowany" in focus_text)
        check("DRAFT article tagged with the SAME concept never appears on the public site",
              "Artykul Roboczy Otagowany" not in focus_text)

        # ---------- root node: corpus roll-up ----------
        page.click('[data-mod="graph"]')
        page.wait_for_timeout(200)
        page.click("#graphIndexConcepts .az-term:has-text('Mysterium Iniquitatis')")
        page.wait_for_timeout(200)
        focus_text = page.locator("#graphFocus").inner_text()
        check("root shows the corpus roll-up heading", "Wszystkie artykuły korpusu" in focus_text)
        check("roll-up includes the deep-tagged published article (via descendant concept)",
              "Artykul Gleboko Otagowany" in focus_text)
        check("roll-up includes the shallow (corpusId-only) published article",
              "Artykul Tylko Korpus" in focus_text)
        check("roll-up groups the deep-tagged article under its branch (uppercased via CSS, compare case-insensitively)",
              "gałąź: synkretyzm" in focus_text.lower())
        check("roll-up puts the untagged-but-corpus-linked article in its own group",
              "bez dalszego tagowania" in focus_text.lower())
        check("DRAFT article tagged with this corpus never appears in the public roll-up",
              "Artykul Roboczy Otagowany" not in focus_text)

        check("no console/page errors", len(errors) == 0)
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
print("CORPUS (PUBLIC SITE) TEST PASSED")

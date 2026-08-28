"""Regression test for the three-level "Os czasu" (timeline) visualization
on the AWA Archiwum public site -- Krok 5 of prompt-archiwum-os-czasu.md
(Kroki 0-4 landed in the admin panel across previous turns; this is the
same visualization, ported to the read-only public site).

Krok 5 was an explicitly open question in the prompt ("czy to samo ma sie
pojawic na archiwum-public... potwierdz w trakcie realizacji, nie zakladaj
bez pytania") -- confirmed by the user before this turn.

Same mechanism as the admin panel's timeline (identical level 1/2/3 logic,
identical CSS class names), with two real differences:
  - data/epochs.json is now fetched in loadAllData() (it wasn't before this
    turn) and EPOCHS assigned the same way CONCEPTS/PERSONS/RELATIONS
    already are.
  - Krok 4's admin-side note explained why "reuse ?article=<id>" did NOT
    apply there (no URL routing in the admin SPA). HERE it genuinely does:
    this site already has a real, working deep link (openArticle() +
    history.pushState, see test_article_deeplink.py) -- calendar rows call
    openArticle(id) directly, the same function Browse/Search/graph
    relation-articles already use.
  - ARTICLES is pre-filtered to status==='published' at load time
    (loadAllData()) -- the level 1-3 render code itself carries no status
    check at all, exactly the same principle already proven for Mapa Pojec
    and Korpusy: a draft's dateRefs must never surface here, verified with
    a draft article tagged identically to a published one.

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py / test_corpus.py (fetch() rejected under file://,
must never touch the real archiwum-public/data/ folder -- which, as of
this turn, holds the user's own real epochs created through the admin
panel; this test builds a completely separate, disposable site copy).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_timeline.py
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
        {"id": "art_pub", "title": "Artykul Opublikowany", "signature": "P-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>T.</p>", "bodyText": "T.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None,
         "status": "published",
         "dateRefs": [{"id": "dr1", "label": "Sobor Nicejski", "epochId": "epoch_mi",
                       "year": 325, "yearEnd": None, "precision": "year", "approximate": False, "note": ""}]},
        {"id": "art_draft", "title": "Artykul Roboczy", "signature": "D-001", "category": "Testy",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>T.</p>", "bodyText": "T.", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-02T00:00:00.000Z", "pdfBase64": None,
         "status": "draft",
         "dateRefs": [{"id": "dr2", "label": "Wydarzenie Robocze", "epochId": "epoch_mi",
                       "year": 325, "yearEnd": None, "precision": "year", "approximate": False, "note": ""}]},
    ]},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": []},
    "persons": {"persons": []},
    "relations": {"relations": []},
    "epochs": {"epochs": [
        {"id": "epoch_mi", "name": "Mysterium Iniquitatis", "startApprox": "", "endApprox": "", "order": 0},
    ]},
    "pages": {"pages": []},
}

site_dir = HERE / "_test_timeline_site"
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

        page.click('[data-mod="timeline"]')
        page.wait_for_timeout(200)

        # ---------- Level 1: only the published article's reference counted ----------
        check("timeline module is shown", page.locator(".timeline-epoch-row").count() == 1)
        count_text = page.locator(".timeline-epoch-block:has-text('Mysterium Iniquitatis') .tl-count").inner_text()
        check("epoch block counts ONLY the published article's reference, not the draft's (1, not 2)",
              count_text == "1")

        # ---------- Level 2/3: the draft's reference never surfaces ----------
        page.click(".timeline-epoch-block:has-text('Mysterium Iniquitatis')")
        page.wait_for_timeout(150)
        check("year chip for 325 shows count 1 (published only)",
              page.locator(".timeline-year-chip:has-text('325')").inner_text().strip().endswith("1"))
        page.click(".timeline-year-chip:has-text('325')")
        page.wait_for_timeout(150)
        calendar_text = page.locator("#timelineView").inner_text()
        check("calendar shows the PUBLISHED reference", "Sobor Nicejski" in calendar_text)
        check("calendar does NOT show the draft article's reference (never fetched into ARTICLES at all)",
              "Wydarzenie Robocze" not in calendar_text)

        # ---------- clicking a calendar entry uses the REAL deep-link mechanism ----------
        page.click(".timeline-calendar-row:has-text('Sobor Nicejski')")
        page.wait_for_timeout(200)
        check("clicking navigates to the article view", page.locator("#articleTitle").inner_text() == "Artykul Opublikowany")
        check("a real ?article= deep-link URL was pushed (the actual existing mechanism, used directly here)",
              "?article=art_pub" in page.url)

        # ---------- reloading that URL lands directly on the article (proves it's a real link, not just in-page state) ----------
        page.goto(f"http://127.0.0.1:{port}/index.html?article=art_pub")
        page.wait_for_function("() => ARTICLES.length > 0")
        check("fresh load of the pushed URL opens the article directly", page.locator("#articleTitle").inner_text() == "Artykul Opublikowany")

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
print("TIMELINE (PUBLIC SITE, KROK 5) TEST PASSED")

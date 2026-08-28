"""Regression test for self-service navigation pages on the AWA Archiwum
public site (prompt-archiwum-samoobslugowe-strony.md) -- the read-only,
published-only side of the feature the admin panel's test_pages.py covers
for the editor.

Krok 0 findings:
  - data/pages.json is fetched the same way as the other collections
    (Promise.all in loadAllData()) and filtered to status==='published'
    right there, the same pattern as ARTICLES -- so renderPagesNav()/
    openPage() never need their own status check.
  - The existing ?article=<id> deep-link (openArticle()/history.pushState,
    with a skipPush flag shared between the popstate handler and the
    initial load) is the exact pattern reused for ?page=<slug> (openPage()) --
    slug instead of id, since that's the human-readable identifier this
    feature is built around.
  - bodyHtml renders through the same .art-body class as article content,
    so heading/italic/blockquote formatting survives with zero extra CSS.

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py (fetch() rejected under file://, must never touch
the real archiwum-public/data/ folder).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_pages.py
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


BASE_FIXTURE = {
    "articles": {"articles": []},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": []},
    "persons": {"persons": []},
    "relations": {"relations": []},
    "epochs": {"epochs": []},
}

PAGES_FIXTURE = {"pages": [
    {"id": "page1", "title": "O projekcie", "slug": "o-projekcie",
     "bodyHtml": "<h2>Naglowek</h2><p>Tresc z <strong>pogrubieniem</strong> i <em>kursywa</em>.</p><blockquote>Cytat blokowy.</blockquote>",
     "navOrder": 0, "status": "published", "createdAt": "", "updatedAt": ""},
    {"id": "page2", "title": "Szkic roboczy", "slug": "szkic-roboczy",
     "bodyHtml": "<p>Nie powinno być widoczne na stronie publicznej.</p>",
     "navOrder": 1, "status": "draft", "createdAt": "", "updatedAt": ""},
    {"id": "page3", "title": "Kontakt", "slug": "kontakt",
     "bodyHtml": "<p>Dane kontaktowe.</p>", "navOrder": 2, "status": "published", "createdAt": "", "updatedAt": ""},
]}


def build_site(site_dir):
    if site_dir.exists():
        shutil.rmtree(site_dir)
    (site_dir / "data").mkdir(parents=True)
    shutil.copy(REPO / "index.html", site_dir / "index.html")
    if (REPO / "assets").exists():
        shutil.copytree(REPO / "assets", site_dir / "assets")
    payload = dict(BASE_FIXTURE)
    payload["pages"] = PAGES_FIXTURE
    for name, data in payload.items():
        (site_dir / "data" / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def serve(site_dir):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---------- normal load: nav filtered to published only ----------
    site1 = HERE / "_test_pages_site1"
    build_site(site1)
    httpd1, port1 = serve(site1)
    page = browser.new_page()
    page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto(f"http://127.0.0.1:{port1}/index.html")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(150)

    nav_items = page.locator("#navPagesDynamic .nav-item")
    check("only the 2 PUBLISHED pages appear in the public nav (draft excluded)", nav_items.count() == 2)
    nav_texts = [nav_items.nth(i).inner_text() for i in range(nav_items.count())]
    check("published pages present, in navOrder", nav_texts == ["O projekcie", "Kontakt"])
    check("the draft page's title never appears anywhere in the public nav", "Szkic roboczy" not in " ".join(nav_texts))

    # ---------- clicking a page: renders content, sets ?page=, breadcrumb back to Start ----------
    nav_items.nth(0).click()
    page.wait_for_timeout(150)
    check("mod-page becomes the active module", page.evaluate("() => document.getElementById('mod-page').classList.contains('active')"))
    check("URL updated to ?page=<slug>", "?page=o-projekcie" in page.url)
    check("title rendered", page.inner_text("#pageTitle") == "O projekcie")
    body_html = page.eval_on_selector("#pageBody", "el => el.innerHTML")
    check("heading formatting preserved", "<h2>Naglowek</h2>" in body_html)
    check("bold formatting preserved", "<strong>pogrubieniem</strong>" in body_html)
    check("italic formatting preserved", "<em>kursywa</em>" in body_html)
    check("blockquote formatting preserved", "<blockquote>Cytat blokowy.</blockquote>" in body_html)
    check("breadcrumb offers a way back to Start", "Start" in page.inner_text("#pageBreadcrumb"))
    page.click("#pageBreadcrumb [data-nav]")
    page.wait_for_timeout(150)
    check("breadcrumb link returns to the Start module", page.evaluate("() => document.getElementById('mod-start').classList.contains('active')"))

    # ---------- draft page has no route: forged ?page=<draft-slug> must NOT open it ----------
    page.goto(f"http://127.0.0.1:{port1}/index.html?page=szkic-roboczy")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(150)
    check("a forged deep-link to a DRAFT page's slug does not open it (falls back to Start)",
          not page.evaluate("() => document.getElementById('mod-page').classList.contains('active')"))

    # ---------- fresh load with ?page=<published-slug> in the URL opens it directly ----------
    page.goto(f"http://127.0.0.1:{port1}/index.html?page=kontakt")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(150)
    check("fresh load with ?page=<published-slug> opens that page directly (not the dashboard)",
          page.evaluate("() => document.getElementById('mod-page').classList.contains('active')"))
    check("correct page opened for the deep-linked slug", page.inner_text("#pageTitle") == "Kontakt")

    # ---------- browser back/forward (popstate) between two pages ----------
    page.goto(f"http://127.0.0.1:{port1}/index.html")
    page.wait_for_function("() => ARTICLES.length >= 0")
    page.wait_for_timeout(150)
    page.click("#navPagesDynamic .nav-item >> nth=0")  # O projekcie
    page.wait_for_timeout(100)
    page.click("#navPagesDynamic .nav-item >> nth=1")  # Kontakt
    page.wait_for_timeout(100)
    page.go_back()
    page.wait_for_timeout(150)
    check("browser back navigates to the previously viewed page (O projekcie)", page.inner_text("#pageTitle") == "O projekcie")
    check("URL reflects the back navigation too", "?page=o-projekcie" in page.url)

    check("no console/page errors across the whole test", len(errors) == 0)
    page.close()
    httpd1.shutdown()
    shutil.rmtree(site1, ignore_errors=True)
    browser.close()

print()
if errors:
    print(f"{len(errors)} FAILURE(S):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("SELF-SERVICE PAGES (PUBLIC SITE) TEST PASSED")

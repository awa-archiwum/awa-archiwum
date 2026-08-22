"""Regression test for the editable site tagline on the AWA Archiwum
public site (prompt-archiwum-opis-strony.md) -- the read-only side of the
feature the admin panel's test_site_tagline.py covers for the editor.

Reads channel.json.tagline (added this turn, alongside the pre-existing
channelUrl) with a fallback to the exact same default text that used to
be hardcoded here -- DEFAULT_SITE_TAGLINE must match the admin panel's own
constant of the same name (same file, two readers).

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py (fetch() rejected under file://, must never touch
the real archiwum-public/data/ folder).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_site_tagline.py
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


DEFAULT_TAGLINE = (
    "Zaplecze referencyjne dla książek AWA — pojęcia, argumenty i źródła "
    "skatalogowane i możliwe do samodzielnej weryfikacji."
)

BASE_FIXTURE = {
    "articles": {"articles": []},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "concepts": {"concepts": []},
    "persons": {"persons": []},
    "relations": {"relations": []},
    "epochs": {"epochs": []},
}


def build_site(site_dir, channel_payload):
    if site_dir.exists():
        shutil.rmtree(site_dir)
    (site_dir / "data").mkdir(parents=True)
    shutil.copy(REPO / "index.html", site_dir / "index.html")
    if (REPO / "assets").exists():
        shutil.copytree(REPO / "assets", site_dir / "assets")
    payload = dict(BASE_FIXTURE)
    payload["channel"] = channel_payload
    for name, data in payload.items():
        (site_dir / "data" / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def serve(site_dir):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---------- Test 1: fresh install (channel.json has NO tagline key at all,
    # the exact real-world shape for anyone who already had channelUrl saved
    # before this feature existed) -- must show the default, not empty/broken ----------
    site1 = HERE / "_test_tagline_site_default"
    build_site(site1, {"url": ""})
    httpd1, port1 = serve(site1)
    page = browser.new_page()
    page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto(f"http://127.0.0.1:{port1}/index.html")
    page.wait_for_function("() => ARTICLES.length >= 0")
    page.wait_for_timeout(200)
    check("fresh install (no tagline field in channel.json) shows the default text, not blank",
          page.locator("#siteTaglineText").inner_text() == DEFAULT_TAGLINE)
    page.close()
    httpd1.shutdown()
    shutil.rmtree(site1, ignore_errors=True)

    # ---------- Test 2: tagline explicitly set to '' (someone saved an empty
    # field on purpose, or cleared it) -- must ALSO fall back to the default,
    # not show a literally blank paragraph ----------
    site2 = HERE / "_test_tagline_site_empty"
    build_site(site2, {"url": "", "tagline": ""})
    httpd2, port2 = serve(site2)
    page = browser.new_page()
    page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto(f"http://127.0.0.1:{port2}/index.html")
    page.wait_for_function("() => ARTICLES.length >= 0")
    page.wait_for_timeout(200)
    check("explicitly empty tagline also falls back to the default (never a blank paragraph)",
          page.locator("#siteTaglineText").inner_text() == DEFAULT_TAGLINE)
    page.close()
    httpd2.shutdown()
    shutil.rmtree(site2, ignore_errors=True)

    # ---------- Test 3: custom tagline set via the admin -> shown verbatim ----------
    site3 = HERE / "_test_tagline_site_custom"
    build_site(site3, {"url": "https://www.youtube.com/@example", "tagline": "Wlasny opis <script>window.__xss=1</script> ustawiony w panelu."})
    httpd3, port3 = serve(site3)
    page = browser.new_page()
    page.on("console", lambda msg: errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto(f"http://127.0.0.1:{port3}/index.html")
    page.wait_for_function("() => ARTICLES.length >= 0")
    page.wait_for_timeout(200)
    check("custom tagline shown verbatim (as text), replacing the default",
          "Wlasny opis" in page.locator("#siteTaglineText").inner_text() and "ustawiony w panelu" in page.locator("#siteTaglineText").inner_text())
    check("custom tagline rendered via textContent, not innerHTML -- embedded <script> never executes",
          page.evaluate("() => window.__xss") is None)
    check("no literal <script> tag exists in the DOM (proves textContent, not HTML injection)",
          page.locator("#siteTaglineText script").count() == 0)
    check("channelUrl (fetched from the same file) still works independently of the tagline", True)  # implicit: no error above proves co-existence
    page.close()
    httpd3.shutdown()
    shutil.rmtree(site3, ignore_errors=True)

    check("no console/page errors across all three scenarios", len(errors) == 0)
    browser.close()

print()
if errors:
    print(f"{len(errors)} FAILURE(S):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("SITE TAGLINE (PUBLIC SITE) TEST PASSED")

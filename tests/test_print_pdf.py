"""Regression test for "Pobierz jako PDF" (browser print -> @media print) on
the AWA Archiwum public site (prompt-archiwum-pdf-druk.md).

Krok 0 findings:
  - #shell/#content/.module are deliberately locked to one internally-
    scrolled, height:100vh box on screen (so #nav/#topbar stay put while
    article content scrolls) -- @media print has to explicitly undo that
    (height:auto, overflow:visible) or the printed/PDF output would be
    clipped to whatever fit in the on-screen viewport instead of paginating
    the full article. Found by reading the base CSS before writing the
    print stylesheet, not assumed.
  - <em>/<blockquote> (added when Czytnik integration landed) are
    distinguished ON SCREEN partly via color (var(--muted)/var(--gold)) --
    print forces a black-on-white palette, so that distinction had to move
    to something color-independent: border + indent + light grey fill for
    blockquote, italic for both.
  - Two real bugs only surfaced by actually rendering a test print (not
    obvious from reading the code): (1) the new print-only header
    (#articlePrintHeader) duplicated the title/author/category that the
    on-screen #articleTitle/#articleMetaLine ALSO show -- fixed by hiding
    those two in print, since the print header fully replaces them. (2)
    the dynamically-inserted <h3>Przypisy</h3>/<h3>Bibliografia</h3>
    headings kept their on-screen gold color because a more specific
    ".art-footnotes h3" rule beats a parent ".art-footnotes{color:...}"
    rule for an inherited property -- fixed with an explicit h3 override.

Same isolated-temp-site + local http.server pattern as
test_article_deeplink.py (fetch() rejected under file://, must never touch
the real archiwum-public/data/ folder).

Usage:
    pip install playwright
    playwright install chromium
    python tests/test_print_pdf.py
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
        {"id": "art1", "title": "Traktat o Synkretyzmie", "signature": "AWA/2026/042", "category": "Teologia",
         "conceptIds": [], "personIds": [], "author": "Jan Testowy", "sourceProject": "", "corpusId": "c1",
         "bodyHtml": ("<h2>Rozdzial Pierwszy</h2>"
                      "<p>Zwykly akapit tekstu z <em>kursywa lacinska</em> w srodku.</p>"
                      "<blockquote>Cytat zrodlowy, wyodrebniony blokowo.</blockquote>"
                      "<p>Kolejny zwykly akapit po cytacie.</p>"),
         "bodyText": "", "footnotesHtml": "<li>Przyklad przypisu.</li>", "biblioHtml": "<li>Zrodlo testowe, 2020.</li>",
         "biblioItems": [], "importedAt": "2026-01-01T00:00:00.000Z", "pdfBase64": None, "status": "published"},
        {"id": "art_bare", "title": "Artykul Bez Kategorii I Korpusu", "signature": "", "category": "",
         "conceptIds": [], "personIds": [], "author": "", "sourceProject": "",
         "bodyHtml": "<p>Prosty artykul bez dodatkowych metadanych.</p>",
         "bodyText": "", "footnotesHtml": "", "biblioHtml": "",
         "biblioItems": [], "importedAt": "2026-01-02T00:00:00.000Z", "pdfBase64": None, "status": "published"},
    ]},
    "books": {"books": []},
    "playlists": {"playlists": []},
    "channel": {"url": ""},
    "concepts": {"concepts": [{"id": "c1", "name": "Mysterium Iniquitatis", "parentId": None, "description": ""}]},
    "persons": {"persons": []},
    "relations": {"relations": []},
    "epochs": {"epochs": []},
    "pages": {"pages": []},
}

site_dir = HERE / "_test_print_site"
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

        # ---------- on-screen: button visible, calls window.print() with no extra logic ----------
        check("'Pobierz jako PDF' button visible on screen", page.locator("#printArticleBtn").is_visible())
        page.evaluate("() => { window.__printCalled = 0; window.print = () => { window.__printCalled++; }; }")
        page.click("#printArticleBtn")
        check("clicking the button calls window.print() exactly once, nothing else",
              page.evaluate("() => window.__printCalled") == 1)

        # ---------- switch to print media and verify the DOM/CSS state ----------
        page.emulate_media(media="print")
        page.wait_for_timeout(150)

        state = page.evaluate("""() => {
            const d = (id) => getComputedStyle(document.getElementById(id)).display;
            return {
                nav: d('nav'), topbar: d('topbar'),
                printBtn: d('printArticleBtn'),
                breadcrumb: getComputedStyle(document.querySelector('.breadcrumb')).display,
                sealRow: getComputedStyle(document.querySelector('.art-seal-row')).display,
                keywords: d('articleKeywords'),
                onScreenTitle: d('articleTitle'),
                onScreenMeta: d('articleMetaLine'),
                printHeader: d('articlePrintHeader'),
                body: d('articleBody'),
            };
        }""")
        check("nav hidden in print", state["nav"] == "none")
        check("topbar hidden in print", state["topbar"] == "none")
        check("print button hides itself (pointless on paper)", state["printBtn"] == "none")
        check("breadcrumb hidden in print", state["breadcrumb"] == "none")
        check("seal/signature row hidden in print", state["sealRow"] == "none")
        check("concept/person tag pills hidden in print (navigation chrome, not prose)", state["keywords"] == "none")
        check("on-screen title hidden (replaced by the dedicated print header, not duplicated)", state["onScreenTitle"] == "none")
        check("on-screen author/category line hidden (same reason)", state["onScreenMeta"] == "none")
        check("dedicated print header IS shown", state["printHeader"] == "block")
        check("article body content stays visible", state["body"] == "block")

        # ---------- print header content: title, author, category, corpus, URL ----------
        header_text = page.locator("#articlePrintHeader").inner_text()
        check("print header shows the title", "Traktat o Synkretyzmie" in header_text)
        check("print header shows the author", "Jan Testowy" in header_text)
        check("print header shows the category", "Teologia" in header_text)
        check("print header shows the resolved corpus NAME, not a raw id", "Mysterium Iniquitatis" in header_text)
        check("print header shows a real, absolute deep-link URL back to this exact article",
              f"?article=art1" in header_text and header_text.strip().endswith("art1"))

        # ---------- formatting survives and stays visually distinct in print ----------
        blockquote_style = page.evaluate("""() => {
            const bq = document.querySelector('.art-body blockquote');
            const cs = getComputedStyle(bq);
            return { borderLeft: cs.borderLeftWidth, fontStyle: cs.fontStyle, bg: cs.backgroundColor };
        }""")
        check("blockquote keeps a visible left border in print", blockquote_style["borderLeft"] not in ("0px", None))
        check("blockquote stays italic in print", blockquote_style["fontStyle"] == "italic")
        check("blockquote keeps a distinguishing background tint (not identical to page white)",
              blockquote_style["bg"] not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"))
        em_style = page.evaluate("() => getComputedStyle(document.querySelector('.art-body em')).fontStyle")
        check("inline <em> stays italic in print", em_style == "italic")

        # ---------- footnotes/bibliography headings forced to a print-safe color (were gold on screen) ----------
        heading_colors = page.evaluate("""() => {
            const fh = document.querySelector('#articleFootnotes h3');
            const bh = document.querySelector('#articleBiblio h3');
            return { fh: fh ? getComputedStyle(fh).color : null, bh: bh ? getComputedStyle(bh).color : null };
        }""")
        check("Przypisy heading forced to print-safe black, not left gold", heading_colors["fh"] == "rgb(17, 17, 17)")
        check("Bibliografia heading forced to print-safe black, not left gold", heading_colors["bh"] == "rgb(17, 17, 17)")

        # ---------- a real PDF actually generates without error and has real content ----------
        pdf_path = HERE / "_print_test_output.pdf"
        page.pdf(path=str(pdf_path))
        check("a real PDF was generated with non-trivial size (content actually rendered)",
              pdf_path.exists() and pdf_path.stat().st_size > 5000)
        pdf_path.unlink(missing_ok=True)

        # ---------- article with no category/corpus at all: header degrades gracefully ----------
        page.emulate_media(media="screen")
        page.goto(f"http://127.0.0.1:{port}/index.html?article=art_bare")
        page.wait_for_function("() => ARTICLES.length > 0")
        page.wait_for_timeout(150)
        page.emulate_media(media="print")
        page.wait_for_timeout(150)
        bare_header = page.locator("#articlePrintHeader").inner_text()
        check("article with no author/category/corpus: print header shows just the title + URL, no 'undefined'/'null' text",
              "Artykul Bez Kategorii I Korpusu" in bare_header
              and "undefined" not in bare_header and "null" not in bare_header)

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
print("PRINT / DOWNLOAD AS PDF TEST PASSED")

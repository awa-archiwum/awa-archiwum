# Testy regresyjne — strona publiczna AWA Archiwum

Nie są częścią samego `index.html` — to narzędzia deweloperskie do
uruchamiania ręcznie po zmianach.

## Instalacja (raz)

```
pip install playwright
playwright install chromium
```

## Uruchamianie

```
python tests/test_article_status.py
python tests/test_article_deeplink.py
```

Kod wyjścia 0 = sukces, 1 = błąd (z opisem asercji).

## `test_article_status.py`

Pilnuje, żeby artykuły ze `status: 'draft'` nigdy nie przeciekały na stronę
publiczną — w żadnym z miejsc, które renderują artykuły (Start, Przeglądarka,
Szukaj, Wykaz źródeł), ani przez Mapę Pojęć (`relation.articleIds`).

`fetch()` plików lokalnych jest odrzucane pod `file://` na poziomie samego
Fetch API w Chromium (nie tylko CORS — sprawdzone empirycznie, że
`page.route()` nawet nie łapie tych żądań, bo request nigdy nie dociera do
warstwy sieciowej), więc ten test serwuje **izolowaną, tymczasową kopię**
`index.html` z własnymi danymi fixture przez lokalny serwer HTTP —
**nigdy** przez prawdziwy folder `data/` tego repo, który może zawierać
prawdziwe, jeszcze niepublikowane/niescommitowane dane (tak było w trakcie
pisania tej funkcji — `data/articles.json`/`data/relations.json` miały
uncommitted zmiany, których ten test świadomie nie dotyka).

Sprawdza: migracja — artykuł bez pola `status` w ogóle traktowany jest jako
`'published'` (ten sam scenariusz co DEFINICJA, patrz README repo); artykuł
roboczy niewidoczny w Start/Przeglądarce/Szukaj/Wykazie źródeł; w Mapie
Pojęć — relacja dokumentowana WYŁĄCZNIE przez artykuł roboczy znika
**całkowicie** (nie tylko traci klikalne źródło — żeby nie ujawniać
istnienia artykułu roboczego przez samą etykietę powiązania), a relacja z
MIESZANYM zestawem (jeden roboczy + jeden opublikowany) zostaje widoczna,
ale jej lista źródeł po kliknięciu pokazuje tylko opublikowany artykuł.

## `test_article_deeplink.py`

Pilnuje `?article=<id>` — dodane razem z kanałem RSS w panelu admina
(`awa-archiwum-admin.html`/`articleFeedLink()`), bo bez tego `<link>`
każdego wpisu kanału musiałby wskazywać na tę samą stronę główną: strona
publiczna wcześniej w ogóle nie miała osobnego, otwieralnego-na-świeżo URL-a
per artykuł (`openArticle()` zmieniał tylko stan DOM, nigdy `location`).

Ta sama izolowana tymczasowa kopia strony + lokalny serwer HTTP co
`test_article_status.py` powyżej (patrz tam po uzasadnienie). Odczekiwanie
na `ARTICLES.length > 0` zamiast stałego `wait_for_timeout()` po każdym
`page.goto()` — złapany podczas pisania tego testu prawdziwy wyścig: zbyt
krótkie/niepewne oczekiwanie czasami łapało `openArticle()` wołane zaraz po
`goto()`, zanim `loadAllData()` zdążyło wypełnić `ARTICLES`, więc wywołanie
cicho nic nie robiło (`if(!a) return`) zamiast pchnąć URL. (Pierwsza wersja
tego czekania sprawdzała `window.ARTICLES` zamiast gołego `ARTICLES` — nie
zadziałało wcale, bo `let ARTICLES` zadeklarowane na szczycie zwykłego,
nie-modułowego `<script>` nie staje się właściwością `window`, tylko samej
przeglądarkowej "global lexical environment" — trzeba odwoływać się do
identyfikatora wprost.)

Sprawdza: świeże wejście z `?article=<id>` (dokładnie kształt URL-a, jaki
generuje kanał RSS) otwiera ten artykuł wprost, bez przechodzenia przez
Start; nieznane/nieopublikowane (robocze) `id` w `?article=` spada z
powrotem do Startu, nie zawiesza się ani nie ujawnia artykułu roboczego
przez samo istnienie takiego URL-a; `openArticle()` faktycznie wpycha
prawdziwy, kopiowalny URL (`history.pushState`), a przejście do innego
modułu w nawigacji czyści nieaktualny parametr, żeby URL nie kłamał o tym,
co jest pokazane; przycisk "Wstecz" przeglądarki (`popstate`) poprawnie
otwiera artykuł, do którego URL-a wraca — nie tylko zmienia pasek adresu
bez odświeżenia widoku.

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

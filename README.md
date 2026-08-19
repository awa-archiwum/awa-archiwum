# Archiwum Wielkiej Apostazji

To repozytorium to wygenerowany wynik (dane + widok publiczny) strony Archiwum Wielkiej Apostazji. Prawdziwe źródło i narzędzie do zarządzania treścią żyje osobno, lokalnie, nie na GitHubie.

## Status artykułu: roboczy / opublikowany

Każdy artykuł ma pole `status: 'draft' | 'published'`. Ten plik (`index.html`) pokazuje wyłącznie artykuły ze `status === 'published'` — we wszystkich miejscach, które renderują artykuły (Start, Przeglądarka, Szukaj, Wykaz źródeł), oraz w Mapie Pojęć: relacja dokumentowana wyłącznie przez artykuł roboczy jest ukrywana **całkowicie** (nie tylko traci klikalne źródło), żeby nie ujawniać istnienia nieopublikowanego artykułu przez samą etykietę powiązania.

**Migracja — świadoma decyzja, nie domysł:** artykuły zapisane przed dodaniem tego pola (brak `status` w `data/articles.json`) są traktowane jako `'published'`, nie `'draft'`. Powód: ta zmiana nie miała nagle ukryć czegoś, co już świadomie było widoczne publicznie (np. artykuł DEFINICJA z jego udokumentowanymi powiązaniami w Mapie Pojęć) tylko dlatego, że powstał przed wprowadzeniem statusu. Nowo importowane artykuły domyślnie dostają `status: 'draft'` w panelu administracyjnym — to jest bufor bezpieczeństwa między importem a publikacją, publikacja wymaga świadomego przełączenia w panelu.

## Kanał RSS (`data/feed.xml`)

RSS 2.0, zawiera wyłącznie artykuły ze `status === 'published'` — dokładnie ten sam filtr co reszta tej strony. Generowany w panelu administracyjnym (`awa-archiwum-admin.html`, `regenerateFeed()`) przy każdym zapisie/przełączeniu statusu/usunięciu artykułu, nie osobnym ręcznym krokiem ani zewnętrznym skryptem — trafia do `git push` razem z resztą `data/*.json`, tak samo ręcznie/świadomie jak wszystko inne w tym repo.

Link do artykułu w każdym wpisie kanału ma postać `?article=<id>` — stąd też deep-linking: `openArticle()` teraz aktualizuje `location` przez `history.pushState()` (wcześniej zmieniał tylko stan DOM, żaden URL nie wskazywał konkretnego artykułu), a świeże wejście na stronę z `?article=<id>` w adresie otwiera od razu ten artykuł zamiast pulpitu startowego. Ikonka "RSS" w górnym pasku i `<link rel="alternate">` w `<head>` prowadzą wprost do `data/feed.xml`.

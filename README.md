# Archiwum Wielkiej Apostazji

To repozytorium to wygenerowany wynik (dane + widok publiczny) strony Archiwum Wielkiej Apostazji. Prawdziwe źródło i narzędzie do zarządzania treścią żyje osobno, lokalnie, nie na GitHubie.

## Status artykułu: roboczy / opublikowany

Każdy artykuł ma pole `status: 'draft' | 'published'`. Ten plik (`index.html`) pokazuje wyłącznie artykuły ze `status === 'published'` — we wszystkich miejscach, które renderują artykuły (Start, Przeglądarka, Szukaj, Wykaz źródeł), oraz w Mapie Pojęć: relacja dokumentowana wyłącznie przez artykuł roboczy jest ukrywana **całkowicie** (nie tylko traci klikalne źródło), żeby nie ujawniać istnienia nieopublikowanego artykułu przez samą etykietę powiązania.

**Migracja — świadoma decyzja, nie domysł:** artykuły zapisane przed dodaniem tego pola (brak `status` w `data/articles.json`) są traktowane jako `'published'`, nie `'draft'`. Powód: ta zmiana nie miała nagle ukryć czegoś, co już świadomie było widoczne publicznie (np. artykuł DEFINICJA z jego udokumentowanymi powiązaniami w Mapie Pojęć) tylko dlatego, że powstał przed wprowadzeniem statusu. Nowo importowane artykuły domyślnie dostają `status: 'draft'` w panelu administracyjnym — to jest bufor bezpieczeństwa między importem a publikacją, publikacja wymaga świadomego przełączenia w panelu.

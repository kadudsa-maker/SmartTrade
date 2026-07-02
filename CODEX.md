# SmartTrade - zasady pracy z Codexem

## Cel projektu

SmartTrade nie jest zwykłym wskaźnikiem.

To terminal do wyszukiwania najlepszych setupów tradingowych.

Priorytety projektu:

- jakość sygnałów
- szybkość działania
- prostota UI
- modułowość
- czytelność kodu
- łatwa rozbudowa

## Zasady pracy

- Nigdy nie przebudowuj działających algorytmów bez wyraźnej prośby.
- Nie zmieniaj wyglądu UI bez polecenia.
- Nie usuwaj istniejących funkcji.
- Nie duplikuj kodu.
- Twórz helpery, gdy zmniejszają powtarzalność albo upraszczają logikę.
- Dbaj o wydajność.
- Minimalizuj liczbę zapytań do API Bybit.
- Nie przebudowuj całego UI podczas odświeżania.
- Aktualizuj tylko elementy, które tego wymagają.
- Zachowuj istniejące granice między UI, wykresem, danymi rynkowymi i logiką sygnałów.
- Przed większą zmianą sprawdź istniejące testy i dopisz nowe tylko tam, gdzie realnie zabezpieczają zachowanie.

## Architektura

### main.py

Punkt startowy aplikacji. Tworzy instancję `SmartTradeUI` i uruchamia główną pętlę programu.

### ui.py

Warstwa interfejsu użytkownika oparta o CustomTkinter. Odpowiada za layout okna, watchlistę, przełączanie interwałów, wybór symbolu, tryby skanowania, odświeżanie kart i przekazywanie danych do wykresu.

Ten moduł może koordynować przepływ danych, ale nie powinien przejmować odpowiedzialności za czyste algorytmy detekcji.

### chart.py

Warstwa rysowania wykresu. Odpowiada za prezentację świec, RSI, pivotów, linii dywergencji, statusów sygnałów i elementów pomocniczych wykresu.

`chart.py` ma renderować przygotowane dane. Reguły wykrywania sygnałów powinny pozostawać poza tym modułem.

### market.py

Warstwa danych rynkowych. Odpowiada za komunikację z Bybit, pobieranie tickerów, świec, list instrumentów, obsługę watchlisty, cache danych i podstawowe obliczenie aktualnego RSI dla listy symboli.

W tym module szczególnie ważne jest ograniczanie liczby zapytań do API.

### divergence.py

Silnik wykrywania dywergencji regularnych RSI. Odpowiada za porównywanie pivotów ceny i RSI, dopasowanie pivotów w czasie oraz budowę struktury znalezionego sygnału.

Nie należy zmieniać reguł dywergencji bez wyraźnej prośby.

### signal_quality.py

Moduł oceny jakości sygnału. Odpowiada za składowe jakości, między innymi siłę pivotów, zmianę RSI i dystans między pivotami.

To naturalne miejsce do rozwoju przyszłego AI Score albo Smart Score, o ile zmiana nie narusza obecnych wyników bez uzgodnienia.

### pivots.py

Moduł wykrywania pivotów ceny i RSI. Odpowiada za algorytm left/right dla Pivot High i Pivot Low oraz przywracanie indeksów RSI po usunięciu pustych wartości.

To wspólny fundament dla dywergencji i jakości sygnałów, więc zmiany wymagają testów regresji.

### time_utils.py

Pomocniczy moduł czasu. Odpowiada za konwersję timestampów i dat do czasu polskiego oraz formatowanie godzin widocznych w aplikacji.

### config.py

Centralne ustawienia działania aplikacji, na przykład minimalna widoczna jakość sygnału i widoczność sygnałów wygasłych.

## Workflow

Przed zmianami:

1. Analiza
2. Plan
3. Implementacja
4. Testy
5. Podsumowanie

Codex powinien najpierw przeczytać odpowiednie moduły, zrozumieć istniejący przepływ danych i dopiero potem wprowadzać małe, kontrolowane zmiany.

## Testy

Po każdej zmianie uruchom:

```bash
python -m py_compile main.py ui.py chart.py market.py divergence.py signal_quality.py pivots.py time_utils.py config.py
python -m pytest
```

Jeżeli zmiana dotyczy wyłącznie dokumentacji, testy nadal można uruchomić jako kontrolę stanu projektu.

## Git

Po każdej większej funkcji:

```bash
git add .
git commit
git push
```

Commit powinien opisywać konkretną zmianę. Nie mieszaj refaktoryzacji, zmian UI, zmian algorytmów i dokumentacji w jednym commicie, jeżeli można je rozdzielić.

## Styl kodu

- Czytelne nazwy.
- Małe funkcje.
- Komentarze tylko tam, gdzie mają sens.
- Brak powielania kodu.
- Helpery zamiast kopiowania logiki.
- Logika detekcji poza UI.
- Renderowanie poza modułami obliczeniowymi.
- Zmiany wydajnościowe mierzone albo jasno uzasadnione.

## Roadmap

Zrealizowane:

- [x] Watchlist
- [x] Top50 Scanner
- [x] Quality
- [x] ACTIVE / AGING / EXPIRED
- [x] Dynamic Scanner
- [x] RSI
- [x] Pivoty
- [x] Dywergencje
- [x] Git
- [x] GitHub
- [x] requirements.txt

Następne etapy:

- [ ] AI Score
- [ ] Hidden Divergence
- [ ] Market Scanner
- [ ] Historia skuteczności sygnałów
- [ ] Powiadomienia
- [ ] Aplikacja Web
- [ ] Aplikacja Android

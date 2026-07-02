# SmartTrade - dokumentacja developerska

Ten dokument opisuje architekturę programu i zasady techniczne dla osób rozwijających SmartTrade.

## Założenia architektury

SmartTrade jest podzielony na warstwy:

- UI i koordynacja: `ui.py`
- Renderowanie wykresu: `chart.py`
- Dane rynkowe i watchlista: `market.py`
- Silnik pivotów: `pivots.py`
- Silnik dywergencji: `divergence.py`
- Ocena jakości sygnałów: `signal_quality.py`
- Czas i formatowanie dat: `time_utils.py`
- Konfiguracja: `config.py`
- Start aplikacji: `main.py`

Najważniejsza reguła: logika detekcji sygnałów ma pozostawać poza UI i poza warstwą rysowania wykresu.

## Przepływ danych

1. `main.py` tworzy i uruchamia `SmartTradeUI`.
2. `ui.py` pobiera watchlistę oraz dane świecowe przez `market.py`.
3. `ui.py` przygotowuje dane świecowe i serię RSI.
4. `pivots.py` wykrywa pivoty ceny i pivoty RSI.
5. `divergence.py` wykrywa regularne dywergencje na podstawie pivotów.
6. `signal_quality.py` liczy składowe jakości dla wykrytych dywergencji.
7. `ui.py` wybiera sygnał do pokazania na kartach i przekazuje dane do `chart.py`.
8. `chart.py` renderuje świece, RSI, pivoty, dywergencje i statusy sygnałów.

## Odpowiedzialność modułów

### main.py

Minimalny punkt wejścia aplikacji. Nie powinien zawierać logiki biznesowej ani logiki UI poza utworzeniem `SmartTradeUI` i wywołaniem `run()`.

### ui.py

Odpowiada za:

- budowę okna aplikacji,
- watchlistę,
- wybór symbolu,
- wybór interwału,
- tryby skanowania,
- odświeżanie kart,
- sortowanie wyników skanera,
- filtrowanie sygnałów po jakości i statusie,
- przekazywanie danych do wykresu.

`ui.py` może koordynować wiele modułów, ale nie powinien zawierać nowych algorytmów detekcji, jeżeli można je przenieść do osobnego modułu.

### chart.py

Odpowiada za:

- przygotowanie obszaru wykresu,
- rysowanie świec,
- rysowanie RSI,
- rysowanie pivotów,
- rysowanie linii dywergencji,
- obsługę crosshaira i etykiet osi,
- wizualizację statusu i jakości sygnału.

`chart.py` nie powinien decydować, czy sygnał istnieje. Powinien jedynie renderować dane otrzymane z warstwy UI.

### market.py

Odpowiada za:

- komunikację z API Bybit,
- pobieranie tickerów,
- pobieranie świec,
- pobieranie dostępnych kontraktów USDT perpetual,
- wybór topowych symboli według obrotu,
- cache danych,
- zapis i odczyt watchlisty,
- reset watchlisty.

W tym module należy szczególnie pilnować wydajności i liczby zapytań do API.

### pivots.py

Odpowiada za:

- wykrywanie Pivot High i Pivot Low dla ceny,
- wykrywanie pivotów RSI,
- obsługę pustych wartości RSI,
- przywracanie oryginalnych indeksów po przygotowaniu serii RSI.

Zmiany w tym module mogą wpłynąć na wszystkie sygnały, więc wymagają testów regresji.

### divergence.py

Odpowiada za:

- wykrywanie Regular Bullish Divergence,
- wykrywanie Regular Bearish Divergence,
- porównywanie kolejnych pivotów ceny,
- dopasowanie pivotów RSI do pivotów ceny,
- budowę struktury dywergencji,
- dołączenie wyniku jakości z `signal_quality.py`.

Nie należy zmieniać reguł dywergencji bez wyraźnego polecenia.

### signal_quality.py

Odpowiada za:

- ocenę siły pivotów,
- ocenę zmiany RSI,
- ocenę dystansu między pivotami,
- wyliczanie końcowego wyniku jakości z komponentów.

To naturalne miejsce na przyszłe rozszerzenia typu AI Score, Smart Score albo dodatkowe komponenty jakości.

### time_utils.py

Odpowiada za:

- aktualny czas polski,
- formatowanie czasu,
- konwersję timestampów i dat do strefy Europe/Warsaw.

### config.py

Przechowuje proste ustawienia działania aplikacji, takie jak minimalna widoczna jakość sygnału i widoczność sygnałów wygasłych.

## Zasady zmian

- Nie przebudowywać działających algorytmów bez wyraźnej prośby.
- Nie zmieniać UI bez polecenia.
- Nie usuwać istniejących funkcji.
- Nie duplikować kodu.
- Tworzyć helpery, gdy zmniejszają powtarzalność.
- Ograniczać zapytania do Bybit.
- Aktualizować tylko te elementy UI, które faktycznie wymagają odświeżenia.
- Trzymać moduły obliczeniowe możliwie niezależne od CustomTkinter.

## Testy

Po każdej zmianie uruchom:

```bash
python -m py_compile main.py ui.py chart.py market.py divergence.py signal_quality.py pivots.py time_utils.py config.py
python -m pytest
```

Aktualne testy obejmują:

- wykrywanie pivotów,
- wykrywanie dywergencji,
- ocenę jakości sygnałów.

## Kierunki rozwoju

- AI Score
- Hidden Divergence
- Market Scanner
- Historia skuteczności sygnałów
- Powiadomienia
- Aplikacja Web
- Aplikacja Android

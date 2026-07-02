# SmartTrade

SmartTrade to terminal do wyszukiwania najlepszych setupów tradingowych na rynku krypto. Projekt łączy watchlistę, skaner rynku, dane z Bybit, RSI, pivoty, dywergencje oraz ocenę jakości sygnałów.

Celem aplikacji nie jest tworzenie kolejnego prostego wskaźnika. SmartTrade ma pomagać szybko znaleźć setupy o najlepszej jakości, przy zachowaniu prostego UI, czytelnej architektury i łatwej rozbudowy.

## Funkcje

- Watchlist instrumentów.
- Pobieranie danych rynkowych z Bybit.
- Top50 Scanner dla kontraktów USDT perpetual.
- Dynamiczne skanowanie symboli.
- Wykres świecowy z panelem RSI.
- Wykrywanie pivotów ceny i RSI.
- Wykrywanie Regular Bullish i Regular Bearish Divergence.
- Ocena jakości sygnału.
- Statusy sygnałów: ACTIVE, AGING, EXPIRED.
- Cache danych ograniczający liczbę zapytań do API.
- Testy jednostkowe dla modułów sygnałowych.

## Wymagania

- Python 3.11 lub nowszy.
- Dostęp do internetu dla danych Bybit.
- System z obsługą aplikacji okienkowych Tkinter/CustomTkinter.

Główne biblioteki:

- customtkinter
- pandas
- pybit
- pytest

Pełna lista zależności znajduje się w `requirements.txt`.

## Instalacja

Sklonuj repozytorium i przejdź do katalogu projektu:

```bash
git clone <repo-url>
cd SmartTrade
```

Utwórz i aktywuj środowisko wirtualne:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Zainstaluj zależności:

```bash
python -m pip install -r requirements.txt
```

## Uruchomienie

```bash
python main.py
```

Aplikacja uruchamia interfejs SmartTrade, ładuje watchlistę i pobiera dane rynkowe z Bybit.

## Testy

Po zmianach w projekcie uruchom:

```bash
python -m py_compile main.py ui.py chart.py market.py divergence.py signal_quality.py pivots.py time_utils.py config.py
python -m pytest
```

## Struktura projektu

```text
SmartTrade/
├── main.py
├── ui.py
├── chart.py
├── market.py
├── divergence.py
├── signal_quality.py
├── pivots.py
├── time_utils.py
├── config.py
├── requirements.txt
├── tests/
├── data/
├── CODEX.md
├── README.md
├── README_DEV.md
└── CHANGELOG.md
```

## Architektura

`main.py` uruchamia aplikację.

`ui.py` odpowiada za interfejs, watchlistę, skaner, wybór symboli i koordynację odświeżania.

`chart.py` odpowiada za rysowanie wykresu, RSI, pivotów i dywergencji.

`market.py` odpowiada za komunikację z Bybit, cache, watchlistę i dane świecowe.

`pivots.py` wykrywa pivoty ceny oraz RSI.

`divergence.py` wykrywa regularne dywergencje RSI.

`signal_quality.py` liczy składowe jakości sygnału.

`time_utils.py` formatuje i konwertuje czas do strefy Europe/Warsaw.

`config.py` przechowuje ustawienia działania aplikacji.

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

## Zasady rozwoju

Szczegółowe zasady pracy z Codexem znajdują się w `CODEX.md`.

Najważniejsze reguły:

- Nie zmieniać UI bez wyraźnego polecenia.
- Nie przebudowywać działających algorytmów bez wyraźnej prośby.
- Nie usuwać istniejących funkcji.
- Minimalizować liczbę zapytań do API Bybit.
- Utrzymywać logikę detekcji poza warstwą UI i wykresu.

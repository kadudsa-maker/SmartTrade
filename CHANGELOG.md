# Changelog

Logiczny opis rozwoju projektu SmartTrade. Wersje porządkują historię funkcji i nie muszą jeden do jednego odpowiadać historii Git.

## v0.1 - Fundament aplikacji

- Utworzenie pierwszej wersji aplikacji.
- Dodanie punktu startowego `main.py`.
- Przygotowanie podstawowego okna programu.
- Rozdzielenie projektu na pierwsze moduły.

## v0.2 - Watchlist

- Dodanie watchlisty instrumentów.
- Obsługa zapisu i odczytu listy symboli z pliku JSON.
- Dodanie mechanizmu resetowania watchlisty do domyślnych symboli.
- Integracja watchlisty z danymi z Bybit.

## v0.3 - Dane rynkowe i RSI

- Dodanie pobierania świec z Bybit.
- Dodanie cache dla danych świec.
- Dodanie obliczania RSI.
- Przygotowanie danych do dalszej analizy sygnałów.

## v0.4 - Wykres

- Dodanie modułu `chart.py`.
- Renderowanie świec i panelu RSI.
- Dodanie warstwy prezentacji pivotów i dywergencji.
- Oddzielenie rysowania od logiki detekcji.

## v0.5 - Pivoty

- Dodanie modułu `pivots.py`.
- Wykrywanie Pivot High i Pivot Low na cenie.
- Wykrywanie pivotów RSI.
- Dodanie testów dla pivotów.

## v0.6 - Dywergencje

- Dodanie modułu `divergence.py`.
- Wykrywanie Regular Bullish Divergence.
- Wykrywanie Regular Bearish Divergence.
- Dopasowanie pivotów ceny i RSI.
- Dodanie testów dla dywergencji.

## v0.7 - Quality

- Dodanie modułu `signal_quality.py`.
- Ocena siły pivotów.
- Ocena siły ruchu RSI.
- Ocena dystansu między pivotami.
- Dodanie wyniku jakości jako składowej sygnału.

## v0.8 - Status sygnałów

- Dodanie statusów ACTIVE, AGING i EXPIRED.
- Filtrowanie sygnałów według jakości i świeżości.
- Uporządkowanie prezentacji sygnałów na watchliście.

## v0.9 - Top50 Scanner

- Dodanie skanera Top50 dla instrumentów USDT perpetual.
- Sortowanie instrumentów według obrotu.
- Dodanie cache listy Top Bybit.
- Wyświetlanie wyników skanera w interfejsie.

## v0.10 - Dynamic Scanner

- Dodanie cyklicznego skanowania symboli.
- Przetwarzanie symboli partiami.
- Aktualizacja tylko wymaganych kart UI.
- Ograniczenie zbędnych odświeżeń i zapytań.

## v0.11 - Porządkowanie projektu

- Dodanie `requirements.txt`.
- Dodanie testów jednostkowych dla kluczowych modułów.
- Uporządkowanie dokumentacji developerskiej.
- Przygotowanie repozytorium do dalszego rozwoju z Codexem.

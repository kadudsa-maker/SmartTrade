# Budowanie SmartTrade dla Windows

## Wymagania

- Windows
- Python 3.11 lub nowszy
- zależności projektu z `requirements.txt`
- PyInstaller

Instalacja zależności i narzędzia do budowania:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

PyInstaller jest zależnością deweloperską i nie jest wymagany przez aplikację
uruchamianą ze źródeł.

## Testy

Przed zbudowaniem aplikacji uruchom:

```powershell
python -m pytest
```

## Build EXE

Standardowe uruchomienie zapyta o potwierdzenie przed usunięciem istniejących
katalogów `build` i `dist`:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

W pełni automatyczny czysty build:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1 -Clean
```

Gotowa aplikacja znajduje się w:

```text
dist\SmartTrade\SmartTrade.exe
```

SmartTrade jest budowany w trybie `onedir`. Katalogi `build` i `dist` są
lokalnymi artefaktami i nie są śledzone przez Git.

## Skrót na pulpicie

Po udanym buildzie utwórz lub odtwórz skrót:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1
```

Skrót wskazuje na `dist\SmartTrade\SmartTrade.exe`. Po każdej zmianie kodu
wykonaj nowy build, aby skrót uruchamiał aktualną wersję aplikacji. Jeśli
repozytorium albo katalog `dist` zostanie przeniesiony, uruchom skrypt skrótu
ponownie.

Konfiguracja i logi użytkownika są zapisywane w
`%LOCALAPPDATA%\SmartTrade`, a nie w katalogu tymczasowym PyInstallera.

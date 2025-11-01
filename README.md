# Semantic-K Weather Chat

Lekka aplikacja demonstracyjna pokazująca architekturę czatu opartego o FastAPI i modele OpenAI. Poniżej znajdziesz szybki przewodnik po konfiguracji lokalnego środowiska na Windowsie.

## Wymagania
- Python 3.10 lub nowszy (`python --version`)
- Klucz API OpenAI z dostępem do modelu wskazanego w `config.yml`

## Instalacja
1. **Klonowanie / pobranie projektu**  
   Upewnij się, że pracujesz w katalogu `e:\PROJECTS\semantic-k`.
2. **Wirtualne środowisko**  
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   Jeżeli PowerShell blokuje aktywację, wykonaj:  
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
3. **Zależności**  
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. **Zmienne środowiskowe**  
   Skopiuj `.env.example` do `.env` i uzupełnij `OPENAI_API_KEY=...`.

## Uruchomienie backendu
- Domyślna wersja serwera:  
  ```powershell
  python simple_server.py
  ```
- Nowa architektura z autoreloadem:  
  ```powershell
  python run.py
  ```
- Alternatywnie skrypt Windows: `start.bat` (sam sprawdzi `config.yml`, `.env` i zależności).

Po starcie backendu interfejs jest dostępny pod `http://localhost:8000`, a dokumentacja API pod `http://localhost:8000/docs`.

## Struktura
- `app/main.py` – punkt wejścia FastAPI (eksportuje `app`)
- `run.py` – uruchamia `uvicorn` z autoreloadem
- `simple_server.py` – uproszczony serwer wykorzystujący konfigurację z `config.yml`
- `config/`, `frontend/`, `app/` – logika aplikacji, konfiguracja oraz pliki UI

## Zatrzymanie pracy
Wciśnij `Ctrl+C` w terminalu, aby wyłączyć serwer. Komenda `deactivate` opuszcza wirtualne środowisko.

Powodzenia!

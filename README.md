# Semantic-K Weather Chat

Aplikacja webowa z interfejsem czatu do interakcji z asystentem pogodowym, wykorzystująca GPT-5 z inteligentnym routingiem opartym na konfiguracji YAML.

## ✨ Funkcje

- **🌤️ Inteligentny Routing**: Automatyczna klasyfikacja promptów jako WEATHER lub OTHER
- **⚙️ Konfiguracja YAML**: Wszystkie ustawienia w jednym pliku `config.yml`
- **📊 Meta Dane**: Wyświetlanie szczegółowych informacji o klasyfikacji
- **💬 Streaming Odpowiedzi**: Przyrostowe wyświetlanie odpowiedzi modelu
- **🎨 Bootstrap 5 UI**: Nowoczesny, responsywny interfejs użytkownika
- **💾 Sesje Czatu**: Historia rozmowy utrzymywana podczas sesji

## 🚀 Szybki Start

### 1. Instalacja

```bash
# Sklonuj repozytorium
git clone <repository-url>
cd semantic-k

# Zainstaluj zależności
pip install -r requirements.txt
```

### 2. Konfiguracja

```bash
# Utwórz plik .env z kluczem API
cp .env.example .env
# Edytuj .env i dodaj: OPENAI_API_KEY=sk-proj-your-key-here
```

### 3. Uruchomienie

```bash
# Linux/Mac
./start.sh

# Windows
start.bat

# Lub ręcznie
python simple_server.py
```

### 4. Użycie

Otwórz przeglądarkę: [http://localhost:8000](http://localhost:8000)

## 📋 Konfiguracja (config.yml)

Cała aplikacja jest konfigurowana przez plik `config.yml`:

```yaml
# Domyślny model
default_model: "gpt-5"

# Dostępne modele
models:
  gpt-5:
    provider: "openai"
    model_id: "gpt-5"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 50000
    temperature: 0.7

# Reguły routingu
routing:
  rules:
    - name: "WEATHER"
      keywords: ["weather", "pogoda", "temperatura", ...]
      preferred_model: "gpt-5"
      system_prompt: "You are a weather information assistant..."
    
    - name: "OTHER"
      keywords: []
      preferred_model: "gpt-5"
      system_prompt: "Przepraszam, ale nie posiadam informacji..."
  
  fallback_model: "gpt-5"
```

### Dostosowanie

#### Dodawanie słów kluczowych
```yaml
keywords: ["weather", "pogoda", "twoje_nowe_slowo"]
```

#### Zmiana promptów systemowych
```yaml
system_prompt: "Twój własny system prompt"
```

#### Zmiana parametrów modelu
```yaml
temperature: 0.8  # 0.0 - 1.0
max_tokens: 100000
```

## 🏗️ Architektura

```
semantic-k/
├── simple_server.py       # ⚙️ FastAPI server (czyta config.yml)
├── config.yml             # 🎯 CAŁA KONFIGURACJA
├── frontend/
│   └── index.html         # 🎨 Bootstrap 5 UI
├── .env                   # 🔑 Klucze API
└── requirements.txt       # 📦 Zależności Python
```

### Przepływ danych

1. **Użytkownik** → Wysyła prompt przez UI
2. **simple_server.py** → Ładuje `config.yml` przy starcie
3. **Klasyfikacja** → Używa `keywords` z config do klasyfikacji
4. **Routing** → Wybiera `preferred_model` z config
5. **Generowanie** → Używa `system_prompt` i parametrów z config
6. **Streaming** → Zwraca odpowiedź do UI

## 🔌 API Endpoints

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/` | GET | Zwraca frontend HTML |
| `/api/chat` | POST | Chat ze streamingiem (SSE) |
| `/api/reset` | POST | Reset sesji czatu |
| `/health` | GET | Health check + info o config |
| `/api/config` | GET | Aktualna konfiguracja (bez kluczy) |

### Przykład użycia API

```bash
# Wysłanie wiadomości
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Jaka jest pogoda?"}'

# Sprawdzenie konfiguracji
curl http://localhost:8000/api/config

# Health check
curl http://localhost:8000/health
```

## 📊 Meta Dane

Każdy prompt generuje następujące meta dane:

```json
{
  "topic": "WEATHER",
  "topic_relevance": 0.75,
  "is_dangerous": 0.0,
  "is_continuation": 0.8,
  "topic_change": 0.1,
  "summary": "Prompt classified as WEATHER with 2 matching keyword(s)."
}
```

## 🛠️ Rozwój

### Uruchomienie w trybie deweloperskim

```bash
# Z hot-reload
uvicorn simple_server:app --reload --host 0.0.0.0 --port 8000
```

### Testowanie

```bash
# Zainstaluj dev dependencies
pip install -r requirements.txt

# Uruchom testy
pytest tests/
```

### Formatowanie kodu

```bash
black simple_server.py
ruff check simple_server.py
```

## 🔧 Troubleshooting

### Błąd: "OPENAI_API_KEY not set"
**Rozwiązanie**: Utwórz plik `.env` z kluczem API

### Błąd: "config.yml not found"
**Rozwiązanie**: Upewnij się, że `config.yml` jest w głównym katalogu

### Błąd: Port 8000 zajęty
**Rozwiązanie**: Zmień port w `simple_server.py` (ostatnia linia)

### Błąd: Model nie działa
**Rozwiązanie**: Sprawdź czy masz dostęp do GPT-5 w swoim kluczu API

## 📝 Przykładowe Prompty

### WEATHER (specjalny system prompt)
- "Jaka jest pogoda w Warszawie?"
- "Will it rain tomorrow?"
- "Temperatura w Krakowie?"

### OTHER (informacja o braku specjalizacji)
- "Co to jest Python?"
- "Napisz funkcję sortującą"
- "Tell me a joke"

## 🌟 Zalety tego rozwiązania

✅ **Centralna konfiguracja** - wszystko w `config.yml`  
✅ **Łatwa modyfikacja** - zmień keywords bez kodu  
✅ **Bezpieczne** - klucze API w `.env`, nie w kodzie  
✅ **Skalowalne** - łatwo dodać nowe modele  
✅ **Przejrzyste** - jasny przepływ danych  

## 📖 Dokumentacja

- [START_HERE.md](START_HERE.md) - Szybki start dla nowych użytkowników
- [config.yml](config.yml) - Komentarze w pliku konfiguracji

## 🤝 Wkład

Pull requesty są mile widziane! Przed wysłaniem PR:

1. Sprawdź formatowanie: `black .`
2. Uruchom linting: `ruff check .`
3. Przetestuj zmiany lokalnie

## 📧 Wsparcie

W razie problemów:
1. Sprawdź [Troubleshooting](#-troubleshooting)
2. Przejrzyj logi serwera
3. Sprawdź [START_HERE.md](START_HERE.md)

## 📜 Licencja

[Dodaj swoją licencję]

---

**Stworzone z ❤️ używając FastAPI, OpenAI GPT-5 i Bootstrap 5**
# Semantic Kernel Weather Chat Application

Aplikacja webowa z interfejsem czatu do interakcji z asystentem pogodowym, wykorzystująca Semantic Kernel oraz inteligentny routing do modeli GPT-5 i Sonnet 4.5.

## ✨ Funkcje

- **🌤️ Inteligentny Routing**: Automatyczna klasyfikacja promptów jako WEATHER lub OTHER
- **📊 Meta Dane**: Wyświetlanie szczegółowych informacji o klasyfikacji:
  - Topic (WEATHER/OTHER)
  - Zgodność z tematem (0-1)
  - Wykrywanie niebezpiecznych promptów (0-1)
  - Wykrywanie kontynuacji rozmowy (0-1)
  - Wykrywanie zmiany tematu (0-1)
  - Podsumowanie klasyfikacji
- **💬 Streaming Odpowiedzi**: Przyrostowe wyświetlanie odpowiedzi modelu
- **🎨 Bootstrap 5 UI**: Nowoczesny, responsywny interfejs użytkownika
- **💾 Sesje Czatu**: Historia rozmowy utrzymywana podczas sesji
- **🔄 Reset**: Możliwość zresetowania rozmowy

## 🚀 Szybki Start

### 1. Instalacja Zależności

```bash
# Instalacja zależności
pip install -e .
```

### 2. Konfiguracja API Keys

Utwórz plik `.env` na podstawie `.env.example`:

```bash
cp .env.example .env
```

Edytuj plik `.env` i dodaj swoje klucze API:

```env
# OpenAI Configuration (dla GPT-5 i GPT-4.1)
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration (dla Sonnet 4.5)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Uruchomienie Serwera

#### Linux/Mac:
```bash
./start_server.sh
```

#### Windows:
```cmd
start_server.bat
```

#### Lub ręcznie:
```bash
python -m uvicorn src.semantic_k.api_server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Otwórz Przeglądarkę

Przejdź do: [http://localhost:8000](http://localhost:8000)

## 🎯 Konfiguracja Modeli

Modele są konfigurowane w pliku `config/config.yml`:

```yaml
default_model: "gpt-5"

models:
  gpt-5:
    provider: "openai"
    model_id: "gpt-5"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 8192
    temperature: 0.7

  sonnet-4.5:
    provider: "anthropic"
    model_id: "claude-sonnet-4.5-20250929"
    api_key_env: "ANTHROPIC_API_KEY"
    max_tokens: 8192
    temperature: 0.7

  gpt-4.1:
    provider: "openai"
    model_id: "gpt-4.1"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 4096
    temperature: 0.7
```

## 📋 Routing Rules

Aplikacja automatycznie klasyfikuje prompty:

### WEATHER (Sonnet 4.5)
- Keywords: weather, pogoda, temperatura, temperature, forecast, prognoza, rain, deszcz, snow, śnieg, sun, słońce, cloud, chmura, wind, wiatr, storm, burza
- System Prompt: "You are a weather information assistant. Provide accurate and helpful weather-related information."

### OTHER (GPT-5)
- Keywords: wszystko inne
- System Prompt: "Przepraszam, ale nie posiadam informacji na ten temat. To nie jest moja dziedzina specjalizacji. Mogę Ci pomóc tylko z informacjami związanymi z pogodą."

## 🎨 Interfejs Użytkownika

### Layout
- **Header**: Tytuł aplikacji i opis
- **Chat Column**: Wyświetlanie historii rozmowy
- **Input Column**: Formularz do wprowadzania promptów
- **Footer**: Meta dane o ostatnim prompcie

### Funkcje UI
- **WYŚLIJ (Ctrl+Enter)**: Wysyła wiadomość do modelu
- **RESET**: Resetuje sesję czatu
- **Streaming**: Odpowiedzi wyświetlane są przyrostowo
- **Meta Dane**: Progress bary i wartości procentowe dla każdej metryki

## 📊 Meta Dane

Dla każdego prompta wyświetlane są następujące informacje:

1. **Topic**: Badge z klasyfikacją (WEATHER/OTHER)
2. **Zgodność z tematem**: Jak dobrze prompt pasuje do tematu (0-100%)
3. **Bezpieczeństwo**: Prawdopodobieństwo niebezpiecznego prompta (0-100%)
4. **Kontynuacja**: Czy to kontynuacja rozmowy (0-100%)
5. **Zmiana tematu**: Czy nastąpiła zmiana tematu (0-100%)
6. **Summary**: Jedno zdanie wyjaśnienia klasyfikacji

## 🏗️ Architektura

```
semantic-k/
├── config/
│   └── config.yml              # Konfiguracja modeli i routingu
├── frontend/
│   └── index.html              # Frontend z Bootstrap 5
├── src/
│   └── semantic_k/
│       ├── api_server.py       # FastAPI backend
│       ├── semantic_k_app.py   # Główna aplikacja SK
│       ├── services/
│       │   ├── classifier_service.py  # Klasyfikacja promptów
│       │   └── llm_service.py         # Zarządzanie modelami
│       └── plugins/
│           └── prompt_router_plugin.py # Plugin routingu
├── start_server.sh            # Skrypt startowy (Linux/Mac)
├── start_server.bat           # Skrypt startowy (Windows)
└── requirements.txt           # Zależności projektu
```

## 🔌 API Endpoints

### POST /api/chat
Wysyła wiadomość do modelu i zwraca streaming odpowiedź.

**Request:**
```json
{
  "prompt": "Jaka jest pogoda w Warszawie?",
  "session_id": "optional-session-id"
}
```

**Response:** Server-Sent Events (SSE) stream
```json
// Metadata event
{"type": "metadata", "data": {...}}

// Chunk events
{"type": "chunk", "data": "text fragment"}

// Done event
{"type": "done"}
```

### POST /api/reset
Resetuje sesję czatu.

**Request:**
```json
{
  "session_id": "session-id-to-reset"
}
```

**Response:**
```json
{
  "session_id": "new-session-id",
  "message": "Session reset successfully"
}
```

### GET /api/models
Lista dostępnych modeli.

### GET /health
Health check endpoint.

## 🛠️ Rozwój

### Struktura Kodu

1. **classifier_service.py**: Logika klasyfikacji promptów
2. **api_server.py**: Backend FastAPI z endpointami
3. **index.html**: Frontend z JavaScript do obsługi streaming

### Dostosowanie

#### Dodanie Nowych Keywords
Edytuj `config/config.yml`:

```yaml
routing:
  rules:
    - name: "WEATHER"
      keywords: ["weather", "pogoda", "custom_keyword"]
      preferred_model: "sonnet-4.5"
```

#### Zmiana System Promptów
Edytuj `config/config.yml`:

```yaml
routing:
  rules:
    - name: "WEATHER"
      system_prompt: "Your custom system prompt here"
```

#### Dodanie Nowych Modeli
Edytuj `config/config.yml`:

```yaml
models:
  your-model:
    provider: "openai"
    model_id: "model-name"
    api_key_env: "API_KEY_ENV_VAR"
    max_tokens: 4096
    temperature: 0.7
```

## 🐛 Troubleshooting

### Problem: Serwer nie startuje
- Sprawdź czy masz zainstalowane wszystkie zależności: `pip install -e .`
- Sprawdź czy plik `.env` istnieje i zawiera poprawne klucze API
- Sprawdź czy port 8000 jest wolny

### Problem: Błąd "Model not found"
- Upewnij się, że masz dostęp do wybranych modeli (GPT-5, Sonnet 4.5)
- Sprawdź czy klucze API są poprawne
- Spróbuj użyć innych modeli (GPT-4, Claude 3)

### Problem: Frontend nie ładuje się
- Sprawdź czy serwer działa na porcie 8000
- Sprawdź ścieżkę do pliku `frontend/index.html` w `api_server.py`
- Sprawdź logi serwera

## 📝 Licencja

[Dodaj swoją licencję]

## 🤝 Wkład

Pull requesty są mile widziane!

## 📧 Kontakt

[Dodaj swoje dane kontaktowe]

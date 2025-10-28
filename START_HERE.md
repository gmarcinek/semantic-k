# 🚀 Jak uruchomić aplikację Weather Chat

## ✅ Szybki start (3 kroki)

### 1️⃣ Zainstaluj zależności

```bash
pip install fastapi uvicorn sse-starlette pyyaml python-dotenv pydantic aiohttp openai httpx
```

### 2️⃣ Utwórz plik `.env` z kluczem OpenAI API

Skopiuj plik `.env.example` do `.env`:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac
```

Następnie edytuj `.env` i dodaj swój klucz OpenAI API:

```env
# OpenAI Configuration (dla GPT-5)
OPENAI_API_KEY=sk-proj-your-key-here
```

**⚠️ WAŻNE**: Musisz mieć klucz API OpenAI z dostępem do GPT-5.

### 3️⃣ Uruchom serwer

```bash
python simple_server.py
```

### 4️⃣ Otwórz przeglądarkę

Przejdź do: **http://localhost:8000**

---

## 🎯 Co możesz robić

- **Pytaj o pogodę** - aplikacja użyje GPT-5 z promptem specjalistycznym dla pogody
- **Pytaj o inne rzeczy** - aplikacja odpowie, że to nie jest jej specjalizacja (GPT-5)
- **Przeglądaj meta dane** - na dole strony zobaczysz klasyfikację każdego prompta
- **Resetuj rozmowę** - kliknij przycisk RESET

---

## 📊 Meta dane

Każdy prompt jest klasyfikowany i wyświetlane są następujące informacje:

1. **Topic**: WEATHER lub OTHER
2. **Zgodność z tematem**: 0-100%
3. **Bezpieczeństwo**: wykrywanie niebezpiecznych promptów
4. **Kontynuacja**: czy to kontynuacja rozmowy
5. **Zmiana tematu**: czy nastąpiła zmiana tematu
6. **Summary**: krótkie wyjaśnienie klasyfikacji

---

## ⚙️ Konfiguracja

Wszystkie ustawienia są w pliku `config.yml`:

```yaml
# Domyślny model
default_model: "gpt-5"

# Konfiguracja modeli
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
      keywords: ["weather", "pogoda", ...]
      preferred_model: "gpt-5"
      system_prompt: "You are a weather information assistant..."
    
    - name: "OTHER"
      keywords: []
      preferred_model: "gpt-5"
      system_prompt: "Przepraszam, ale nie posiadam informacji..."
```

### Dodawanie nowych słów kluczowych

Edytuj `config.yml` i dodaj nowe słowa do sekcji `keywords`:

```yaml
routing:
  rules:
    - name: "WEATHER"
      keywords: ["weather", "pogoda", "twoje_nowe_slowo"]
```

### Zmiana promptów systemowych

Edytuj `config.yml` w sekcji `system_prompt`:

```yaml
routing:
  rules:
    - name: "WEATHER"
      system_prompt: "Twój własny prompt systemowy"
```

---

## 🛠️ Troubleshooting

### Problem: "OPENAI_API_KEY not set in environment variables"

**Rozwiązanie**: Utwórz plik `.env` i dodaj klucz API:
```env
OPENAI_API_KEY=sk-proj-your-key-here
```

### Problem: "config.yml not found"

**Rozwiązanie**: Upewnij się, że plik `config.yml` znajduje się w tym samym katalogu co `simple_server.py` lub w podkatalogu `config/`

### Problem: Serwer nie startuje

**Rozwiązanie**: Sprawdź czy:
1. Zainstalowałeś wszystkie zależności: `pip install fastapi uvicorn sse-starlette pyyaml python-dotenv pydantic openai`
2. Masz plik `.env` z kluczem API OpenAI
3. Masz plik `config.yml` w odpowiednim miejscu
4. Port 8000 jest wolny

### Problem: Port 8000 jest zajęty

**Rozwiązanie**: Edytuj `simple_server.py` i zmień port (ostatnia linia):
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # zmień na 8001
```

---

## 📝 Przykładowe prompty

### Prompty WEATHER (będą obsługiwane ze specjalnym promptem)
- "Jaka jest pogoda w Warszawie?"
- "What's the weather like today?"
- "Czy będzie padać deszcz?"
- "Will it snow tomorrow?"
- "Temperatura w Krakowie"

### Prompty OTHER (będą odrzucane)
- "Co to jest Python?"
- "Napisz mi funkcję"
- "Tell me a joke"
- "Jak ugotować makaron?"

---

## 🎨 Funkcje interfejsu

- **Streaming odpowiedzi**: Tekst pojawia się przyrostowo
- **Typing indicator**: Animacja podczas generowania odpowiedzi
- **Progress bary**: Wizualizacja meta danych
- **Responsywny design**: Działa na desktop i mobile
- **Bootstrap 5**: Nowoczesny wygląd

---

## 🔧 Technologie

- **FastAPI**: Backend API
- **Uvicorn**: ASGI server
- **OpenAI SDK**: Integracja z GPT-5
- **Bootstrap 5**: Frontend UI
- **Server-Sent Events**: Streaming odpowiedzi
- **PyYAML**: Konfiguracja z pliku YAML

---

## 💻 Dla developerów

### Struktura projektu
```
semantic-k/
├── simple_server.py           # 🎯 GŁÓWNY SERWER (używa config.yml)
├── config.yml                 # ⚙️ CAŁA KONFIGURACJA TUTAJ
├── frontend/
│   └── index.html             # UI aplikacji
├── .env                       # Klucze API (utwórz ten plik!)
├── .env.example               # Przykładowy plik .env
└── START_HERE.md              # Ta dokumentacja
```

### API Endpoints

- `GET /` - Zwraca frontend HTML
- `POST /api/chat` - Chat endpoint ze streamingiem (SSE)
- `POST /api/reset` - Reset sesji czatu
- `GET /health` - Health check + info o konfiguracji
- `GET /api/config` - Zwraca aktualną konfigurację (bez kluczy API)

### Jak działa system konfiguracji

1. **Startup**: `simple_server.py` ładuje `config.yml` przy starcie
2. **Klasyfikacja**: Używa słów kluczowych z `config.yml` do klasyfikacji
3. **Routing**: Wybiera model z `config.yml` na podstawie klasyfikacji
4. **Generowanie**: Używa parametrów modelu z `config.yml` (temperature, max_tokens)
5. **Prompt systemowy**: Wstawia system prompt z `config.yml`

### Testowanie konfiguracji

```bash
# Sprawdź czy config jest poprawny
python simple_server.py

# W logach zobaczysz:
# ==================================================
# Starting Weather Chat Application
# ==================================================
# Default model: gpt-5
# Available models: ['gpt-5']
# Routing rules: ['WEATHER', 'OTHER']
# ==================================================
```

Możesz też sprawdzić endpoint:
```bash
curl http://localhost:8000/api/config
```

---

## 📞 Wsparcie

Jeśli masz problemy:
1. Sprawdź czy masz plik `.env` z kluczem OpenAI API
2. Sprawdź czy plik `config.yml` istnieje i jest poprawny
3. Sprawdź czy wszystkie pakiety są zainstalowane
4. Sprawdź logi serwera w terminalu
5. Sprawdź czy port 8000 jest wolny

---

**Powodzenia! 🚀**

## 🔄 Migracja z poprzedniej wersji

Jeśli używałeś poprzedniej wersji z Anthropic:

1. **Usuń** `ANTHROPIC_API_KEY` z pliku `.env`
2. **Zostaw** tylko `OPENAI_API_KEY` w `.env`
3. **Nadpisz** `config.yml` nową wersją (tylko GPT-5)
4. **Uruchom** ponownie: `python simple_server.py`

Teraz wszystko działa tylko z OpenAI i config.yml! 🎉
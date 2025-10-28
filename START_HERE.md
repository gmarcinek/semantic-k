# 🚀 Jak uruchomić aplikację Weather Chat

## ✅ Szybki start (3 kroki)

### 1️⃣ Zainstaluj zależności

```bash
pip install fastapi uvicorn sse-starlette pyyaml python-dotenv pydantic aiohttp openai anthropic httpx jinja2
```

### 2️⃣ Utwórz plik `.env` z kluczami API

Skopiuj plik `.env.example` do `.env`:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac
```

Następnie edytuj `.env` i dodaj swoje klucze API:

```env
# OpenAI Configuration (dla GPT-4/GPT-5)
OPENAI_API_KEY=sk-proj-your-key-here

# Anthropic Configuration (dla Claude Sonnet)
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**⚠️ WAŻNE**: Musisz mieć **przynajmniej jeden** z tych kluczy API:
- `OPENAI_API_KEY` - do obsługi promptów OTHER (domyślnie GPT-4)
- `ANTHROPIC_API_KEY` - do obsługi promptów WEATHER (Claude Sonnet)

### 3️⃣ Uruchom serwer

```bash
python simple_server.py
```

### 4️⃣ Otwórz przeglądarkę

Przejdź do: **http://localhost:8000**

---

## 🎯 Co możesz robić

- **Pytaj o pogodę** - aplikacja użyje Claude Sonnet (jeśli masz klucz Anthropic)
- **Pytaj o inne rzeczy** - aplikacja odpowie, że to nie jest jej specjalizacja (GPT-4)
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

## 🛠️ Troubleshooting

### Problem: "OPENAI_API_KEY not set in environment variables"

**Rozwiązanie**: Utwórz plik `.env` i dodaj klucz API:
```env
OPENAI_API_KEY=sk-proj-your-key-here
```

### Problem: "ANTHROPIC_API_KEY not set in environment variables"

**Rozwiązanie**: Dodaj klucz Anthropic do pliku `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Problem: Serwer nie startuje

**Rozwiązanie**: Sprawdź czy:
1. Zainstalowałeś wszystkie zależności: `pip install fastapi uvicorn sse-starlette ...`
2. Masz plik `.env` z kluczami API
3. Port 8000 jest wolny

### Problem: Port 8000 jest zajęty

**Rozwiązanie**: Edytuj `simple_server.py` i zmień port:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # zmień na 8001
```

---

## 📝 Przykładowe prompty

### Prompty WEATHER (będą obsługiwane przez Claude Sonnet)
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
- **OpenAI SDK**: Integracja z GPT
- **Anthropic SDK**: Integracja z Claude
- **Bootstrap 5**: Frontend UI
- **Server-Sent Events**: Streaming odpowiedzi

---

## 💻 Dla developerów

### Struktura projektu
```
semantic-k/
├── simple_server.py           # 🎯 GŁÓWNY SERWER (TEN UŻYWAMY!)
├── frontend/
│   └── index.html             # UI aplikacji
├── .env                       # Klucze API (utwórz ten plik!)
├── .env.example               # Przykładowy plik .env
├── START_HERE.md              # Ta dokumentacja
└── README_CHAT.md             # Szczegółowa dokumentacja
```

### API Endpoints

- `GET /` - Zwraca frontend HTML
- `POST /api/chat` - Chat endpoint ze streamingiem (SSE)
- `POST /api/reset` - Reset sesji czatu
- `GET /health` - Health check

### Modyfikacja modeli

Edytuj `simple_server.py`:

```python
# Dla WEATHER - linia 196
model="claude-3-5-sonnet-20241022"  # Zmień model

# Dla OTHER - linia 168
model="gpt-4"  # Zmień model
```

---

## 📞 Wsparcie

Jeśli masz problemy:
1. Sprawdź czy masz plik `.env` z kluczami API
2. Sprawdź czy wszystkie pakiety są zainstalowane
3. Sprawdź logi serwera w terminalu
4. Sprawdź czy port 8000 jest wolny

---

**Powodzenia! 🚀**

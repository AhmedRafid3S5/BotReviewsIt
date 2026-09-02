# Samsung Phone Query & Review System

A retrieval-augmented, multi-agent assistant for Samsung phones. It scrapes phone
specifications from GSMArena into SQLite, builds a local embedding index over them, and
answers questions or writes full product reviews through a LangChain multi-agent system —
exposed as a FastAPI backend with a Streamlit chat UI on top.

```
GSMArena ──► scraper.py ──► SQLite (phones.db) ──► rag.py (embedding index)
                                   │                      │
                                   ▼                      ▼
                            agents.py (LangChain multi-agent system)
                                   │
                                   ▼
                            api.py (FastAPI backend, :8000)
                                   │  HTTP (JSON)
                                   ▼
                            app.py (Streamlit chat UI, :8501)
```

| File | Role |
|---|---|
| [`scraper.py`](scraper.py) | Scrapes 12 Samsung phone spec pages from GSMArena (requests + BeautifulSoup) |
| [`database.py`](database.py) | SQLite schema and all read/write helpers |
| [`rag.py`](rag.py) | Embeds spec chunks with local Ollama `nomic-embed-text`; cosine-similarity retrieval |
| [`agents.py`](agents.py) | Orchestrator (router) + SpecAgent (retrieval) + ReviewAgent (writer) |
| [`api.py`](api.py) | FastAPI endpoints for phones, Q&A, and reviews |
| [`app.py`](app.py) | Streamlit chat interface, a pure HTTP client of the API |
| [`config.py`](config.py) | Reads `.env`; model names, hosts, API key, DB path |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Developed on 3.12. `api.py` uses `list[dict]` syntax, so 3.9 and older will not work. |
| **[Ollama](https://ollama.com/download)** installed and running locally | Used only for **embeddings** (`nomic-embed-text`). Serves on `http://localhost:11434`. |
| **Ollama Cloud API key** | Used for the **chat model** (`gemma4:31b-cloud`). Create one at [ollama.com](https://ollama.com) under account settings → keys. |
| **Internet access** | For the initial GSMArena scrape and for all cloud LLM calls. |

The chat model runs in Ollama's cloud while the embedding model runs on your machine, so
you need both the API key *and* a local Ollama daemon.

---

## 1. Clone

```bash
git clone <your-repo-url> ReviewBot
```

```bash
cd ReviewBot
```

## 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
```

```powershell
venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, allow it for the current session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Windows (cmd):**

```bat
venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
python3 -m venv venv && source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

Installs `requests`, `beautifulsoup4`, `python-dotenv`, `langchain`, `langchain-ollama`,
`fastapi`, `uvicorn`, `streamlit`, and `numpy`.

## 4. Set up Ollama (embeddings)

Install Ollama, then pull the embedding model:

```bash
ollama pull nomic-embed-text
```

Verify the daemon is up — this should return a JSON list of models:

```bash
curl http://localhost:11434/api/tags
```

On Windows and macOS the Ollama desktop app starts the daemon automatically; otherwise run
`ollama serve` in its own terminal.

## 5. Create the `.env` file

`.env` is gitignored, so it does not come with the clone. Create it in the project root:

```ini
OLLAMA_API_KEY=your_ollama_cloud_api_key_here
OLLAMA_HOST=https://ollama.com
OLLAMA_MODEL=gemma4:31b-cloud
EMBED_HOST=http://localhost:11434
EMBED_MODEL=nomic-embed-text
API_URL=http://localhost:8000
```

| Key | Meaning | Default if omitted |
|---|---|---|
| `OLLAMA_API_KEY` | Bearer token for Ollama Cloud (**required**) | `""` |
| `OLLAMA_HOST` | Host serving the chat model | `https://ollama.com` |
| `OLLAMA_MODEL` | Chat model used by all three agents | `gemma4:31b-cloud` |
| `EMBED_HOST` | Host serving the embedding model | `http://localhost:11434` |
| `EMBED_MODEL` | Embedding model | `nomic-embed-text` |
| `API_URL` | Where the Streamlit UI looks for the backend | `http://localhost:8000` |

Every key except `OLLAMA_API_KEY` has a working default in [`config.py`](config.py), so for
a standard local setup a `.env` containing just the API key is enough.

## 6. Build the database

`phones.db` is gitignored too, so a fresh clone has no data. Populate it in two steps.

**a. Scrape GSMArena** — takes roughly two minutes, since there is a deliberate 5-second
delay between requests (GSMArena rate-limits aggressively):

```bash
python scraper.py
```

This crawls the Samsung listing pages to discover each phone's URL, parses the spec
tables, and writes 12 phones with roughly 680 spec rows into `phones.db`. Re-running
replaces a phone's existing rows rather than duplicating them.

To scrape only a subset, pass name fragments as arguments:

```bash
python scraper.py S23 S24
```

**b. Build the embedding index** — requires the local Ollama to be running:

```bash
python rag.py
```

This creates one chunk per phone per spec category (plus a short overview chunk), embeds
each with `nomic-embed-text`, and stores the vectors as blobs in the `embeddings` table —
about 180 chunks for the full 12-phone set. It prints one line per phone as it goes.

Both steps are one-time. Re-run `rag.py` whenever you re-scrape, since indexing clears and
rebuilds the whole table.

## 7. Run the app

Two processes in two terminals — **both with the virtual environment activated**.

**Terminal 1 — the API:**

```bash
uvicorn api:app --port 8000
```

Add `--reload` during development. The agent system is constructed once at startup, so the
first request after boot is no slower than the rest.

**Terminal 2 — the UI:**

```bash
streamlit run app.py
```

Streamlit opens `http://localhost:8501` in your browser. The sidebar lists every phone in
the database and offers a one-click **Write review** button; the chat box sends each
question, plus recent history, to the API.

---

## Using the API directly

Interactive Swagger docs: <http://localhost:8000/docs>

| Endpoint | Method | Purpose |
|---|---|---|
| `/phones` | GET | List all phones in the database |
| `/phones/{name}` | GET | Full spec sheet for one phone (fuzzy name match) |
| `/ask` | POST | `{"question": ..., "history": [...]}` → routed agent answer |
| `/review/{name}` | GET | Generated product review for a phone |

```bash
curl http://localhost:8000/phones
```

```bash
curl "http://localhost:8000/phones/S23%20Ultra"
```

```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"Which Samsung phone has the best battery life?\", \"history\": []}"
```

```bash
curl "http://localhost:8000/review/Samsung%20Galaxy%20S24%20Ultra"
```

`/ask` returns `{"agent": "qa" | "review", "answer": "..."}` — the `agent` field tells you
which specialist the orchestrator routed the query to.

### Things to try in the chat UI

- `What is the display size of the Galaxy S23 Ultra?` — exact spec lookup
- `Compare the S22 Ultra and the S24 Ultra cameras` — multi-phone retrieval
- `Which phone has the biggest battery?` — comparison across RAG hits
- `Write a review of the Galaxy Z Fold5` — routed to the ReviewAgent

---

## Phones in the dataset

Galaxy S21 5G · S21 Ultra 5G · S22 5G · S22 Ultra 5G · S23 · S23 Ultra · S24 · S24 Ultra ·
Z Flip5 · Z Fold5 · A54 · A34

---


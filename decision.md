# TripMint Architecture & Implementation Decisions

This document logs all major and minor technical decisions, fixes, and architecture choices made during the development of the **TripMint AI Travel Agent** codebase.

---

## 1. Environment & Security Setup
- **Decision:** Ignored `venv/`, `.env`, `__pycache__/` in `.gitignore`.
- **Reason:** Keeps confidential API keys out of version control and prevents committing heavy local Python dependencies.

---

## 2. Configuration Management (`config.py`)
- **Decision:** Built a centralized `config.py` class that calls `load_dotenv()` once at application boot.
- **Reason:** Avoids repeating `os.getenv()` calls across every tool and backend file, provides IDE autocompletion, and allows single-point key validation.

---

## 3. Flight Search Tool (`tools/flight_tool.py`)
- **Decision:**
  - Resolved `BASE_URL` and `AIRPORTS` dataset variable typos.
  - Implemented `certifi.where()` for SSL certificate verification.
  - Built regex and alias location resolver (`resolve_location_to_iata`) for countries and cities (e.g., India ➡️ DEL, Japan ➡️ NRT).
- **Reason:** Fixes runtime `NameError` crashes, handles SSL handshake issues on Windows/Docker, and translates natural language queries into valid IATA airport codes for AviationStack API.

---

## 4. Web Search Tool (`tools/tavily_tool.py`)
- **Decision:** Used `.rsplit(" ", 1)[0] + "..."` for truncating snippets over 500 characters.
- **Reason:** Prevents truncating words in half (unlike simple slicing) while keeping prompt tokens concise for LLMs.

---

## 5. LangGraph Multi-Agent Backend (`backend.py`)
- **Decision:**
  - Standardized `TypedDict` import and schema.
  - Fixed `content=` keyword argument syntax inside `SystemMessage` and `HumanMessage`.
  - Aligned `llm_calls` state counter across all 4 agent nodes (`flight_agent`, `hotel_agent`, `itinerary_agent`, `master_agent`).
  - Removed `conn.close()` inside the execution function `run_travel_agent()`.
  - Set `search_flights(query, limit=3)` in `flight_agent`.
  - Used `qwen/qwen3.8-27b` via Groq.
- **Reason:**
  - Fixes `ImportError` and `TypeError` crashes during graph execution.
  - Prevents Postgres connection death on multi-turn user requests.
  - Keeps total prompt tokens within Groq's free-tier rate limit (8,000 TPM).

---

## 6. Execution & Encoding (`test.py`)
- **Decision:** Wrapped `sys.stdout` with a UTF-8 text encoder (`encoding='utf-8'`).
- **Reason:** Resolves Windows terminal `UnicodeEncodeError` when rendering emojis (✈️, 🏨, ⛩️) and non-ASCII characters in AI outputs.

---

## 7. Web Application & Frontend Architecture (`app.py`, `index.html`, `style.css`, `script.js`)
- **Decision:**
  - Configured FastAPI with `BASE_DIR = Path(__file__).resolve().parent` for relative static asset (`/static`) and template (`/templates`) mounting.
  - Implemented `POST /api/plan` endpoint connected to `run_travel_agent()`.
  - Built a modern dark glassmorphic UI (`index.html` + `style.css`) with tabbed outputs (Master Plan, Live Flights, Hotels, Itinerary), agent progress simulation steps, and Markdown rendering using `marked.js`.
- **Reason:** Provides a sleek, responsive, wow-factor web UI for end-users, isolates agent outputs into clean inspectable tabs, and preserves `thread_id` in `localStorage` for multi-turn session continuity.



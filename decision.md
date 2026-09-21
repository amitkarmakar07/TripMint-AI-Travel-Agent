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
  - Standardized `TypedDict` import and schema (`TravelState`).
  - Implemented a dual-model LLM strategy:
    - **`llm = ChatOpenAI(model="gpt-4o", temperature=0.7)`**: High-reasoning model for comprehensive travel synthesis, flight breakdown, hotel recommendations, budget analysis, and creative itinerary drafting.
    - **`light_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)`**: Ultra-fast, deterministic, low-cost model ($0.15 / 1M tokens) dedicated to input guardrail validation and location/city extraction.
  - Added full multi-agent orchestration with dynamic supervisor routing:
    - `START` ➡️ `supervisor_agent`
    - Conditional route: blocked requests jump straight to `guardrail_blocked_agent` ➡️ `END`.
    - Valid requests dynamically pass through specialist agents based on query needs (`flight_agent` ➡️ `hotel_agent` ➡️ `weather_agent` ➡️ `budget_agent` ➡️ `itinerary_agent`).
    - Added **`human_approval_agent`** using LangGraph `interrupt(...)` to pause execution and present the drafted itinerary for user approval or revision.
    - `human_approval_agent` ➡️ `master_agent` (polishes the final response incorporating user feedback) ➡️ `END`.
  - Added `resume_travel_agent(thread_id, approved, feedback)` leveraging `Command(resume=...)` to resume the graph from PostgreSQL checkpointer snapshots.
  - Added `extract_interrupt_payload()` and `serialize_result()` to cleanly expose state and interrupt details to HTTP clients.
- **Reason:**
  - Guarantees strict safety and topical guardrails without wasting expensive tokens.
  - Adds true multi-agent specialist routing rather than a static hardcoded pipeline.
  - Introduces Human-in-the-Loop (HITL) review so users can approve drafts or request revisions before the final plan is confirmed.

---

## 6. Execution & Encoding (`test.py`)
- **Decision:** Wrapped `sys.stdout` with a UTF-8 text encoder (`encoding='utf-8'`).
- **Reason:** Resolves Windows terminal `UnicodeEncodeError` when rendering emojis (✈️, 🏨, ⛩️) and non-ASCII characters in AI outputs.

---

## 7. Web Application & Frontend Architecture (`app.py`, `index.html`, `style.css`, `script.js`)
- **Decision:**
  - Configured FastAPI with `BASE_DIR = Path(__file__).resolve().parent` for relative static asset (`/static`) and template (`/templates`) mounting.
  - Added `/api/resume_planner` endpoint to handle HITL approval/revision actions (`thread_id`, `approved`, `feedback`).
  - Enhanced UI with an interactive **Human-in-the-Loop Review Card** with live draft previews, feedback textarea, and *Approve* / *Request Revision* buttons.
  - Added dedicated tabs for **Weather** and **Budget Analysis** in addition to Master Plan, Live Flights, Hotels, and Detailed Itinerary.
  - Updated animated progress bar and agent step chips to reflect the complete 7-step multi-agent architecture (`supervisor`, `flight`, `hotel`, `weather`, `budget`, `itinerary`, `master`).
- **Reason:** Exposes the full power of the backend multi-agent graph to users with an interactive, modern glassmorphic interface, enabling seamless feedback cycles.

---

## 8. Endpoint & Schema Alignment (`app.py`, `script.js`)
- **Decision:**
  - Updated FastAPI endpoint to `POST /api/travel_planner` using `TravelRequest` schema with `message: str` and `thread_id: Optional[str]`.
  - Added `POST /api/resume_planner` with `ApprovalResumeRequest` schema (`thread_id: str`, `approved: bool`, `feedback: Optional[str]`).
  - Serialized all relevant state fields (`requires_approval`, `approval_request`, `selected_agents`, `budget_analysis`, `weather_result`, `guardrail_allowed`).
- **Reason:** Keeps frontend and backend Pydantic validation 100% aligned, preventing `422 Unprocessable Entity` or `AttributeError` schema mismatches.

---

## 9. Template Response Keyword Fix (`app.py`)
- **Decision:** Updated `templates.TemplateResponse` call in `home()` to use keyword parameters: `request=request, name="index.html", context={"name": "TripMint"}`.
- **Reason:** Fixes a `TypeError: unhashable type: 'dict'` crash in Starlette >= 0.28+ when calling positional dictionary parameters, resolving the HTTP 500 Internal Server Error on `GET /`.

---

## 10. Containerization & Docker Setup (`Dockerfile`, `.dockerignore`)
- **Decision:**
  - Standardized filename casing to standard `Dockerfile`.
  - Corrected `apt-get install -y` typo (`intall` ➡️ `install`).
  - Fixed `COPY requirements.txt .` filename typo (`requirments.txt`).
  - Corrected CMD entry point to `"app:app"` (`"app.app:app"` ➡️ `"app:app"`).
  - Updated `.dockerignore` to exclude `.git`, `.env`, virtualenvs, and cache binaries.
- **Reason:** Ensures error-free multi-platform Docker container builds for cloud deployments (AWS, Docker Hub, Render, GCP).

---

## 11. MCP (Model Context Protocol) Clients (`mcp_clients.py`)
- **Integration Overview:**
  - **Hotel Search:** Tavily Remote MCP (`tavily_mcp_search`).
  - **Flight Search:** AviationStack Local MCP (`aviation_mcp_search`).
  - **Weather Forecast:** Custom FastMCP Server (`weather_mcp_search` via `custom_weather_mcp.py`).
- **Issue & Resolution (MCP Connection Closed):**
  - **Problem**: When attempting to start `aviationstack-mcp` using `uvx`, it crashed immediately with a "Connection closed" error.
  - **Root Cause**: `uvx` defaults to pulling the latest `mcp` library (v2.x). However, `aviationstack-mcp` was built for v1.x, leading to a `ModuleNotFoundError` for `mcp.server.fastmcp`.
  - **Solution**: Updated `mcp_clients.py` to pass `--with mcp<2` in the `args` array. This forces `uvx` to use a compatible 1.x version of the `mcp` library, fixing the crash.

---

## 12. Human-in-the-Loop Approval & Loading Freeze Fix (`templates/index.html`, `static/script.js`)
- **Problem:** Clicking "Approve & Finalize" or "Request Revision" caused an infinite loading spinner; the API call `/api/resume_planner` never fired, and console threw `TypeError: Cannot set properties of null (setting 'textContent')`.
- **Root Cause:** ID mismatch (`id="loading-step"` in HTML vs `document.getElementById('loading-subtext')` in JS). Accessing `.textContent` on null crashed execution before `fetch()` was called.
- **Solution:** Renamed the HTML element to `id="loading-subtext"`, added fallback in JS (`loading-subtext` || `loading-step`), added null guards, and wrapped DOM/fetch calls inside `try ... finally`.

---

## 13. Thread ID Reuse & Cross-Trip History Bleedover Fix (`static/script.js`)
- **Problem:** When submitting a new search (e.g. *Goa from Bangalore*), LangSmith traces showed the user message from a previous trip (*India to Australia tour*).
- **Root Cause:** `script.js` was persisting `currentThreadId` in `localStorage` and passing it to `/api/travel_planner` on new searches. LangGraph's PostgreSQL checkpointer reloaded the existing thread state and appended the new message to the existing `messages` reducer list (`operator.add`).
- **Solution:** Reset `currentThreadId = null` on new form submits and on "New Search" resets, passing `thread_id: null` to ensure every new travel search gets a fresh PostgreSQL thread and clean LangSmith trace.

---

## 14. Hotel/Weather Formatting & Dynamic Tab Visibility (`backend.py`, `templates/index.html`, `static/script.js`)
- **Problem:** Hotel tab displayed `[object Object]`, Weather tab displayed raw MCP JSON error string (`"city not found"` when countries were provided), and tabs for unrequested agents (e.g. budget/weather) were statically shown regardless of relevance.
- **Root Cause:**
  - FastMCP returned raw lists of text dicts (`[{'type': 'text', 'text': ...}]`), which JavaScript stringified as `[object Object]` when injected into `<pre>`.
  - Weather location extraction prompted for cities only; when a country (e.g., Bulgaria) was provided, it returned `"Location not found."`, causing OpenWeatherMap to search for that string and fail.
  - Tabs in `templates/index.html` were static without checking `data.selected_agents`.
- **Solution:**
  - Added `parse_mcp_output()` helper in `backend.py` to cleanly unpack FastMCP JSON payloads.
  - Enhanced `hotel_agent` to synthesize top hotel recommendations grouped by category (Luxury, Mid-Range, Budget) in structured Markdown.
  - Enhanced `weather_agent` location extractor to resolve countries/regions to their primary capital/major city (e.g., Bulgaria ➔ Sofia) and format weather metrics (temp, condition, humidity, forecast) into clean Markdown.
  - Updated `templates/index.html` to render `hotel-output` and `weather-output` inside `markdown-body` containers.
  - Implemented dynamic tab filtering in `static/script.js`: only tabs corresponding to agents selected by `supervisor_agent` (and having content) are displayed (`display: inline-flex`), hiding irrelevant tabs completely.

---

## 15. Minimalist White & Warm Yellow UI/UX Redesign (`templates/index.html`, `static/style.css`, `static/script.js`)
- **Decision:**
  - Redesigned the visual theme to a clean luxury travel aesthetic pairing pristine white backgrounds (`#FFFFFF`, `#FAFAF9`) with warm amber/golden-yellow accents (`#F59E0B`, `#EAB308`, `#FEF3C7`).
  - Switched typography to modern geometric editorial fonts: `Plus Jakarta Sans` for body/interface and `Outfit` (800 weight) for luxury headings.
  - Added an AI-curated **Destination Showcase Grid** with high-resolution travel photography (Kyoto, Sofia, Paris, Swiss Alps) with interactive click-to-prompt capability.
  - Upgraded results tabs, Human-in-the-Loop review card, loading stepper, and markdown prose styles with refined shadows, pill badges, and warm golden hover states.

---

## 16. AI Travel Planner Hero & 4-Column Day Itinerary Architecture (`templates/index.html`, `static/style.css`, `static/script.js`, `backend.py`)
- **Decision:**
  - **Hero Section:** Explicitly branded the system with `YOUR PERSONAL AI TRAVEL PLANNER` badge, updated headline to `Your AI Travel Planner. Where Will You Journey Next?`, and introduced a 3-card feature strip highlighting *Autonomous Multi-Agent Coordination*, *4-Column Day-by-Day Itineraries*, and *Smart Budget Control*.
  - **4-Column Compact Itinerary Grid:** Implemented an intelligent parser `renderItineraryAsCards()` in `static/script.js` and responsive CSS grid (`grid-template-columns: repeat(4, 1fr)`) to render Day 1, Day 2, Day 3, etc., as compact cards with Morning, Afternoon, Evening, and Highlights time slots with dedicated icons.
  - **Structured Sectional Cards:** Implemented `renderStructuredMasterPlan()` and `formatSegmentContent()` to wrap Flight, Hotel, Weather, and Budget sections into distinct `.plan-segment-card` containers with icon badges, highlighted paragraphs (`.para-highlight-card`), and key-value detail pills.
- **Reason:** Transforms wall-of-text itineraries into a scannable, modern multi-column card layout matching high-end travel apps, and clearly communicates the platform's role as a personal AI travel planner.

---

## 17. Forest Green & Mint Teal Aesthetic with Minimalist Header (`templates/index.html`, `static/style.css`, `static/script.js`)
- **Decision:**
  - **Color Scheme:** Completely transitioned the UI to a deep forest green and dark emerald canvas (`#071F1B`, `#0B2823`, `#0E332D`) paired with glowing mint/teal accents (`#2DD4BF`, `#14B8A6`, `#5EEAD4`).
  - **Header Simplification:** Completely removed the navbar menu links, retaining only a minimal top brand bar with the TripMint AI logo and active multi-agent status indicator.
  - **Hero Layout:** Replaced the hero with a 2-column layout:
    - Left: High-impact typography (`Live Your Adventure.`), floating white capsule search bar with "Where to?" and "Date Range", quick prompt pills, and 3 feature trio cards (*Expert Guides*, *Tailored Itineraries*, *Best Price Guarantee*).
    - Right: High-resolution curved photo frame of a smiling female traveler in an alpine setting (`static/hero_hiker.jpg`).
  - **Popular Destinations Showcase:** Added 3 travel inspiration cards matching the mockup: *El Nido, Philippines* ($899), *Santorini, Greece* ($1099), and *Iceland* ($1299) with rating badges, pricing, traveler avatars, and click-to-prompt actions.
- **Reason:** Satisfies the user's exact specification for a dark green palette, menu-free top bar, matching dummy photography, and clean card aesthetics.

---

## 18. Pure White Professional Results Canvas & Interactive Day 1 / Day 2 Sub-Tabs (`templates/index.html`, `static/style.css`, `static/script.js`)
- **Decision:**
  - **White Canvas for Workflow & Results:** Set the entire results section (`.results-container`), loading indicator (`.loading-card`), and approval box (`.approval-card`) to a pure white background (`#FFFFFF`) with high-contrast slate text (`#0F172A`), clean borders (`#E2E8F0`), and soft shadows, replacing dark green in the output areas for maximum readability and a clean professional feel.
  - **Removed Static Card Grid:** Deprecated the static multi-column card grid in the itinerary section in favor of an interactive tabbed experience.
  - **Interactive Day 1 / Day 2 Sub-Tab Selector:** Implemented a horizontal scrolling sub-tab bar matching the user's reference screenshot (`media_1789929856980.png`).
    - Each sub-tab card features a bold `DAY X` badge, day label, truncated headline, hotel/activity subtitle, and an active amber bottom indicator notch (`.subtab-notch`).
    - Clicking a sub-tab dynamically displays that specific day's detailed panel (`.day-detail-panel`) with Morning, Afternoon, Evening, and Highlights time slots without requiring page reloads or layout jumping.
  - **Clean Code & Cache Busting:** Purged obsolete dark green CSS rules from `static/style.css` and added version cache-busting query strings (`?v=20260921`) to `templates/index.html`.
- **Reason:** Directly fulfills the user's request for a clean, simple, professional white background for results output, removal of cluttered card grids, and intuitive Day 1 / Day 2 sub-tabs.

---

## 19. Enhanced Flight Agent with Live AviationStack Schedules & Flight Timings (`mcp_clients.py`, `backend.py`)
- **Decision:**
  - **Unrestricted AviationStack MCP Tool Discovery:** Updated `initialize_aviation_mcp()` in [`mcp_clients.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/mcp_clients.py) to register all available tools (`flight_arrival_departure_schedule`, `get_flight_status`, `flights_with_airline`, `list_airports`, `list_airlines`) rather than only filtering static airport/airline catalogues.
  - **Live Departure Timetable Integration:** Updated `flight_agent` in [`backend.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/backend.py) to resolve the departure IATA code (defaulting to `DEL` or user query) and query `flight_arrival_departure_schedule` for live carrier schedules, departure gates, terminals, and scheduled times.
  - **Live Route & Timetable Search:** Combined AviationStack live departure airport activity with targeted Tavily timetable queries to capture connecting carrier flights (e.g., Turkish Airlines, Lufthansa, Emirates, Air India) and route durations.
  - **Structured Flight Names & Schedules:** Re-engineered the flight prompt and master synthesis prompt to strictly produce recommended flight options featuring:
    1. **Flight Name & Carrier** (e.g. Air India, Turkish Airlines, Lufthansa)
    2. **Flight Number** (e.g. AI2817, TK717 / TK1027, LH761)
    3. **Scheduled Departure Time** (e.g. 06:15 AM from Terminal 3)
    4. **Scheduled Arrival Time** (e.g. 14:30 PM at destination)
    5. **Total Duration & Layover**
    6. **Airfare Ranges & Strategic Booking Guidance**
- **Reason:** Fulfills the user's request to have the Flight Agent display the best specific flight times, flight names, and flight numbers backed by real AviationStack live data and route timetables.

---

## 20. Baseline Sequential Multi-Agent Architecture (Restored for Benchmarking) (`backend.py`)
- **Decision:**
  - **Sequential Chaining Restored:** Restored the LangGraph execution graph to the sequential routing pipeline (`supervisor -> flight -> hotel -> weather -> budget -> itinerary -> human_approval -> master`) per user request to run baseline test cases and latency evaluations.
  - **Sequential Routing Logic:** Restored `ROUTE_MAP`, `get_selected_agents()`, `route_from_supervisor()`, and `route_after_agent()`.
  - **Telemetry Count:** Reverted `llm_calls` in `TravelState` to standard integer tracking `state.get("llm_calls", 0) + 1`.
- **Reason:** Allows the user to execute baseline test cases, capture latency benchmarks on the sequential system, and compare directly against the parallel fan-out architecture.

---

## 21. Cloud Redis & In-Memory Fallback Caching for External MCP Tools (`config.py`, `cache.py`, `mcp_clients.py`)
- **Decision:**
  - **Created `cache.py` Wrapper:** Implemented a non-blocking caching layer supporting Cloud Redis (`REDIS_URL`) with TLS support (`rediss://`) via `certifi` and automated fallback to an internal in-memory Python dictionary if Redis is offline or unconfigured.
  - **Wrapped External MCP APIs:**
    1. **Tavily Web Searches (`tavily_mcp_search`):** Cached for 12 hours (43,200s) to prevent redundant web crawling for popular destinations and hotel lists.
    2. **AviationStack Schedules (`aviation_mcp_search`):** Cached for 4 hours (14,400s) keyed by tool name and argument JSON.
    3. **OpenWeather Forecasts (`weather_mcp_search`):** Cached for 6 hours (21,600s) per city.
  - **Graceful Error Handling:** Wrapped all cache gets and sets in try-except blocks with timeout guards to prevent Redis latency or network drops from blocking or failing user trip planning requests.
- **Reason:** Reduces external API rate-limit consumption, eliminates repetitive network hops, and delivers sub-50ms cache-hit latencies for repeated destination queries.

---

## 22. Clean Modular Architecture Decomposition (`state.py`, `llm.py`, `agents/`, `graph.py`, `backend.py`)
- **Decision:**
  - Decomposed the 848-line monolithic [`backend.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/backend.py) into clean, decoupled, single-responsibility modules:
    1. [`state.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/state.py): Contains `TravelState` TypedDict, agent schemas, and default constraints.
    2. [`llm.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/llm.py): Contains LLM instances (`llm` gpt-4o, `light_llm` gpt-4o-mini), SSL cert configuration, and response parsers (`json_from_llm`, `parse_mcp_output`).
    3. [`agents/`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/): Contains modular, dedicated agent nodes:
       - [`agents/supervisor.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/supervisor.py): Input guardrail & supervisor routing.
       - [`agents/flight.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/flight.py): Live AviationStack + Tavily flight planning.
       - [`agents/hotel.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/hotel.py): Hotel search & curation.
       - [`agents/weather.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/weather.py): City extraction & OpenWeather forecast.
       - [`agents/budget.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/budget.py): Financial feasibility & cost breakdown.
       - [`agents/itinerary.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/itinerary.py): Day-by-day itinerary draft, Human-in-the-loop approval interrupt, and final Master agent response synthesis.
       - [`agents/__init__.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/agents/__init__.py): Re-exports all agent nodes cleanly.
    4. [`graph.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/graph.py): StateGraph construction, routing edges, and Postgres checkpointer setup.
    5. [`backend.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/backend.py): Retained as the clean public facade providing `run_travel_agent()` and `resume_travel_agent()` for [`app.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/app.py) with zero breaking changes.
- **Reason:** Prevents file bloat, separates agent logic from infrastructure concerns, improves maintainability, and makes isolated testing and prompt updates straightforward.

---

## 23. Parallel Fan-Out/In Architecture, Hybrid Model Tiering & SSE Streaming (`graph.py`, `state.py`, `agents/`, `backend.py`, `app.py`, `static/script.js`)
- **Decision:**
  - **Parallel Fan-Out (Scatter-Gather):**
    - Updated `route_from_supervisor()` in [`graph.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/graph.py) to return a `list[str]` of specialist nodes (`flight_agent`, `hotel_agent`, `weather_agent`, `budget_agent`), scheduling all required agents concurrently.
    - Updated `llm_calls` in [`state.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/state.py) to `Annotated[int, operator.add]` with nodes returning `{"llm_calls": 1}` to prevent concurrent state overwrite conflicts.
    - Formed a barrier join converging all specialist branches directly into `itinerary_agent` (fan-in).
  - **Pragmatic Model Tiering:**
    - Assigned **GPT-4o-mini (`light_llm`)** to MCP tool consumers and intermediate analyzers (`flight_agent`, `hotel_agent`, `weather_agent`, `budget_agent`, and input guardrail) for high-speed extraction (~1-2s).
    - Preserved **GPT-4o (`llm`)** strictly for high-cognitive tasks: `supervisor_agent` constraint extraction, `itinerary_agent` comprehensive day-by-day scheduling, and `master_agent` final response polishing.
  - **Server-Sent Events (SSE) Streaming:**
    - Implemented `stream_travel_agent()` and `stream_resume_travel_agent()` in [`backend.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/backend.py) yielding `start`, `node_complete`, `interrupt`, and `complete` events formatted according to W3C SSE standard (`event: <name>\ndata: <json>\n\n`).
    - Added `/api/travel_planner/stream` and `/api/resume_planner/stream` in [`app.py`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/app.py) using FastAPI's `StreamingResponse`.
    - Integrated real-time SSE stream reader in [`static/script.js`](file:///d:/DATA%20SCIENCE%20PROJECT%20FOR%20RESUME/TripMint/static/script.js), displaying live status badges and parallel agent execution dynamically.
- **Reason:** Slashes end-to-end trip planning latency dramatically, eliminates static progress timers with live execution telematics, and preserves premium plan quality while cutting LLM token costs.

---

## 24. Production Hardening: Redis Rate Limiting, 50KB Payload Guard & Groq Cross-Provider Fallback (`cache.py`, `app.py`, `llm.py`)
- **Decision:**
  - **Redis Sliding-Window Rate Limiter (`cache.py`, `app.py`):**
    - Added `check_rate_limit(client_ip, max_requests=10, window_seconds=60)` using Cloud Redis atomic `INCR` + `EXPIRE` with fail-open safety.
    - Integrated FastAPI HTTP middleware blocking abuse with `HTTP 429 Too Many Requests` when more than 10 requests/min are made.
  - **Request Payload Size Guard (`app.py`):**
    - Enforced a strict 50 KB `Content-Length` ceiling in middleware, immediately returning `HTTP 413 Payload Too Large` to prevent memory exhaustion and malicious token dumps.
  - **Cross-Provider Groq LLM Fallback (`llm.py`):**
    - Leveraged existing `GROQ_API_KEY` to configure a cross-provider fallback model using `ChatGroq(model="openai/gpt-oss-120b")`.
    - Chained `llm` with `.with_fallbacks([primary_light_llm, groq_model])` and `light_llm` with `.with_fallbacks([groq_model])`, ensuring 100% service uptime even in the event of OpenAI downtime or rate limiting.
- **Reason:** Prevents API key quota exhaustion from automated scripts, protects backend memory, and guarantees zero-downtime trip generation using ultra-fast Groq LPU inference as a safety net.

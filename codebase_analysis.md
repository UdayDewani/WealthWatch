# WealthWatch 2.0 — Full Codebase Analysis

## 1. Directory Structure

```
WealthWatch/
├── AGENT_CONTEXT.md          # Agent handoff / decision log
├── backend/
│   ├── .env                  # Local secrets (GEMINI_API_KEY empty)
│   ├── config.py             # All env-var loading
│   ├── main.py               # FastAPI app + ingestor loop + lifespan
│   ├── requirements.txt      # Python deps
│   ├── wealthwatch.db        # SQLite file (live, WAL mode active)
│   ├── agents/
│   │   └── market_graph.py   # LangGraph pipeline
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt_handler.py    # bcrypt + jose JWT
│   │   └── dependencies.py   # FastAPI Depends helpers
│   ├── data/
│   │   ├── database.py       # aiosqlite ORM-lite
│   │   ├── multi_asset_client.py  # yfinance wrapper
│   │   └── redis_cache.py    # redis.asyncio hot cache
│   └── web/
│       ├── __init__.py
│       ├── routes.py         # All REST + WebSocket endpoints
│       └── ws_manager.py     # Broadcast manager
└── frontend/
    ├── index.html
    ├── package.json          # React 18 + Vite 5 + TypeScript 5 only
    ├── vite.config.ts        # Proxy: /api /auth /ws → localhost:4040
    ├── tsconfig.json
    └── src/
        ├── App.tsx           # Auth gate + page router (state machine)
        ├── main.tsx
        ├── index.css         # Full design system (~850 lines)
        ├── api/
        │   ├── auth.ts       # JWT localStorage + fetch helpers
        │   ├── clients.ts
        │   ├── deposits.ts
        │   ├── investments.ts
        │   └── market.ts     # REST + WebSocket factory
        ├── types/
        │   └── market.ts     # Shared TS interfaces
        └── components/
            ├── Login.tsx
            ├── Sidebar.tsx
            ├── Dashboard.tsx
            ├── Clients.tsx
            ├── Markets.tsx
            ├── Recommendations.tsx
            ├── ClientModal.tsx
            ├── DepositModal.tsx
            └── InvestmentModal.tsx
```

---

## 2. Architecture & End-to-End Request Flow

### A. Real-time Market Tick (background loop)

```
Backend startup (lifespan)
  └─▶ asyncio.create_task(ingestor_loop())
        every ANALYSIS_INTERVAL seconds (default 60s):
          ├─ [optional] NewsFetcher.fetch_market_news() → news[]
          ├─ [optional] UpstoxClient.get_live_index_data() → upstox_data{}
          ├─ run_market_analysis(market_data, news)
          │     └─ LangGraph graph.invoke(initial_state)
          │           analyze_node → parse_node → END
          │           returns analysis{}
          ├─ redis_cache.set_broadcast(broadcast{})
          ├─ redis_cache.set_snapshot(snapshot{})
          ├─ [hourly] db.save_market_snapshot() + db.save_market_analysis()
          └─ ws_manager.broadcast(broadcast{})
                └─ pushes JSON to all active WebSocket clients
```

### B. Frontend WebSocket Consumption

```
Dashboard.tsx mounts
  └─ createWebSocket() → new WebSocket('/ws')   [proxied to :4040]
        ws.onmessage → JSON.parse → setMarketData()
        → propagated up to App via onMarketData()
        → Recommendations receives marketData as prop
```

### C. HTTP Request Flow (WM managing clients)

```
Browser (Vite :5000)
  → authFetch('/api/clients', { headers: Bearer <jwt> })
  → Vite proxy → FastAPI :4040
  → router.get('/api/clients')
  → Depends(require_wm) → decode JWT → verify role=='wm'
  → _db.get_clients(wm_id)
  → enriched with deposit/investment totals
  → JSON response
```

### D. Manual AI Analysis (Recommendations page)

```
User clicks "Run Analysis"
  → authFetch POST /api/market/trigger-analysis
  ⚠️ THIS ROUTE DOES NOT EXIST IN routes.py
```

### E. Portfolio with Live P&L

```
GET /api/clients/{id}/portfolio
  → db.get_deposits() + db.get_investments()
  → for each open investment:
      _get_live_price(symbol) via yfinance.Ticker.fast_info
      (run in asyncio.to_thread)
  → calculates unrealized P&L per holding
  → returns full portfolio dict
```

---

## 3. LangGraph Agent Graph

### State Schema — `MarketState` (TypedDict)
| Field | Type | Description |
|---|---|---|
| `market_data` | `Dict[str, Any]` | Raw market dict: indices, stocks, news, timestamp |
| `news` | `list` | List of news item dicts |
| `raw_analysis` | `str` | Raw LLM response string |
| `analysis` | `Dict[str, Any]` | Parsed structured analysis |
| `error` | `str` | Error string (set in state but **never written to**) |

### Graph Topology
```
[START]
  └─▶ analyze_node
        └─▶ parse_node
              └─▶ [END]
```
Linear pipeline — no conditional edges, no branching.

### Node Details

**`analyze_node`**
- Instantiates `ChatGoogleGenerativeAI` (gemini-2.5-flash) on every call (no caching)
- Builds a text prompt with `indices` JSON + top 5 news headlines
- Invokes LLM synchronously (LangChain `.invoke()`)
- Strips markdown fencing if present
- Writes `raw_analysis` (str) to state
- Falls back to `raw_analysis = ""` if API key missing or LLM call fails

**`parse_node`**
- Parses `raw_analysis` as JSON → writes `analysis` dict
- Falls back to `_fallback_analysis()` (rule-based from Nifty change_pct) if parse fails or raw is empty

**`_fallback_analysis()`**
- Pure Python heuristic: `change_pct > 0.3` → bullish, `< -0.3` → bearish, else neutral
- Returns the full schema with static hardcoded risks/opportunities/sectors

### Execution
- `run_market_analysis()` is `async` and wraps the synchronous `graph.invoke()` in `asyncio.to_thread()`
- Graph is a module-level singleton (`_graph`), built once on first call
- LLM client is re-instantiated inside `analyze_node` on every tick — no connection pooling

---

## 4. External Dependencies & Integrations

| Dependency | Purpose | Status |
|---|---|---|
| **Gemini (gemini-2.5-flash)** via `langchain-google-genai` | LLM analysis | Configured; needs `GEMINI_API_KEY` in `.env` (currently empty) |
| **yfinance** | Live prices for multi-asset + portfolio P&L | Installed; works without API key; rate-limited |
| **Upstox API** | Live Indian index data (Nifty/Sensex) | Optional; `data/upstox_client.py` does NOT exist; graceful no-op |
| **Yahoo Finance news** | News headlines for LLM prompt | Optional; `data/yahoo_fetcher.py` does NOT exist; graceful no-op |
| **SQLite (aiosqlite)** | Primary persistent store | Active (`wealthwatch.db` exists with WAL) |
| **Redis** | Hot cache for market broadcast + snapshots | Optional; gracefully disabled if not running |
| **WebSocket** | Real-time push to frontend | Fully implemented |
| **JWT (python-jose + bcrypt)** | Auth for WM and client roles | Fully implemented |

---

## 5. Configuration & Environment

### `config.py` — All variables loaded from `.env` via `python-dotenv`

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `4040` | Backend server port |
| `GEMINI_API_KEY` | `""` | **Empty in .env — AI analysis is a no-op currently** |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model name |
| `JWT_SECRET` | `wealthwatch-dev-secret-change-in-prod` | **Insecure default in .env** |
| `JWT_ALGORITHM` | `HS256` | Hardcoded in config.py |
| `JWT_EXPIRE_HOURS` | `24` | |
| `REDIS_URL` | `redis://localhost:6379` | Commented out in .env |
| `UPSTOX_API_KEY` | `""` | Optional, commented out |
| `SNAPSHOT_INTERVAL_HOURS` | `1` | How often market data is persisted to SQLite |
| `ANALYSIS_INTERVAL` | `60` | Ingestor loop tick in seconds |

### Dev vs Prod
- **No environment separation** — single `.env` file, no `.env.production` or env-based config switching
- JWT secret is a weak default in the committed `.env`
- `reload=True` on uvicorn (dev mode) is hardcoded when running `python main.py`

---

## 6. Code Health Assessment

### ✅ Solid Patterns
- `asyncio.to_thread()` used correctly to avoid blocking the event loop for yfinance calls
- Graceful degradation for optional services (Upstox, Redis, News)
- LangGraph fallback analysis so the app never crashes on LLM failure
- Clean JWT implementation with role-based guards (`require_wm` / `require_client`)
- WAL mode + foreign keys enabled on SQLite
- Vite proxy config correctly set up (resolves a known issue from AGENT_CONTEXT)

### ⚠️ Issues & Gaps

**Critical (breaks features)**
1. **`POST /api/market/trigger-analysis` missing** — `Recommendations.tsx` calls this route but it doesn't exist in `routes.py`. The "Run Analysis" button will always return a 404.
2. **`GET /api/market/analysis/history` missing** — `Recommendations.tsx` calls this too. History will never load.
3. **CORS mismatch** — `main.py` allows `localhost:5000` and `localhost:4040`, but the Vite dev server runs on **port 5000** (correct!). However, if any other port is used it will break.
4. **`GEMINI_API_KEY` is empty** — AI analysis is silently a no-op; the fallback fires every tick.

**Medium (fragile or incomplete)**
5. **LLM client re-instantiated every tick** — `_get_llm()` is called inside `analyze_node`, which runs every 60 seconds. No connection reuse.
6. **`client_own_portfolio` endpoint is broken** — Uses `client_portfolio.__wrapped__` which doesn't exist since there's no `@functools.wraps` decorator. Falls back to `_build_portfolio`, but `_build_portfolio` hardcodes `realized_pnl: 0` instead of computing it.
7. **`MarketState.error` field is never written** — It's in the TypedDict but no node ever sets it.
8. **yfinance rate limiting** — Portfolio endpoint calls `yf.Ticker.fast_info` for each open investment serially; can be slow and rate-limited with many holdings.
9. **No `get_all_assets()` method** — `routes.py` calls `_asset_client.get_all_assets()` but `MultiAssetClient` only defines `get_asset_overview()`. This will cause a `AttributeError` on the `/api/markets/assets` endpoint.
10. **`AnalysisResult` type mismatch** — Frontend `types/market.ts` expects `recommendations` and `risks` arrays on `AnalysisResult`, but the LLM prompt returns `key_risks`, `opportunities`, and `recommended_sectors`. The Recommendations page's recommendation/risk cards will never render.
11. **`Recommendations.tsx` never navigated to from Dashboard** — `onAnalysis` prop is passed but `_onAnalysis` is unused (prefixed with `_`). The user can only get there via Sidebar.

**Low priority**
12. **No tests** — Zero test files anywhere (no pytest, no vitest)
13. **No pagination** on any list endpoints (clients, investments, history)
14. **`delete_client` doesn't verify ownership success** — Returns `{"message": "Deleted"}` even if no rows were affected
15. **`get_deposits` has no WM ownership check** — A WM can GET any client's deposits if they know the `client_id`
16. **JWT token is never validated for expiry refresh** — 24h sessions, no refresh token
17. **No input sanitization** beyond Pydantic models
18. **`wealthwatch.db` is committed to the repo structure** (`.db`, `.db-shm`, `.db-wal` visible in listing)

---

## 7. Working vs. Missing Functionality

### ✅ Fully Working
- WM registration and JWT login
- Client CRUD (create, list, update, delete)
- Deposit recording and listing
- Investment recording, closing, deletion
- Portfolio summary with live yfinance prices and P&L
- WebSocket push to Dashboard
- Redis hot cache (when Redis is running)
- SQLite persistence with WAL
- Vite dev proxy (ports correct)
- Login/Logout UI flow
- Dashboard with AUM stats + client table
- `GET /api/markets/assets` → **almost** working (see bug #9 below)

### ⚠️ Partially Working / Broken at Runtime
- **Markets page** — Will crash with `AttributeError: 'MultiAssetClient' object has no attribute 'get_all_assets'` (method is named `get_asset_overview`)
- **Recommendations page** — "Run Analysis" button is broken (missing route). Analysis history never loads (missing route). Even if analysis arrives via WebSocket, the `recommendations`/`risks` arrays won't render because of the schema mismatch.
- **LangGraph AI Analysis** — Runs on every tick but Gemini key is empty, so it only produces fallback output. The graph itself is valid and will work once the key is set.
- **Client portal** (`/api/client/me/portfolio`) — Endpoint exists but `realized_pnl` is hardcoded to 0

### ❌ Not Built (Planned/Stubbed)
- `data/upstox_client.py` — Not created
- `data/yahoo_fetcher.py` — Not created (no real news data)
- Client Portal UI (`/portal` route) — Not started
- `POST /api/market/trigger-analysis` — Not implemented
- `GET /api/market/analysis/history` — Not implemented
- Any test suite

---

## 8. Summary

### Architecture
```
React (Vite :5000)
  ↕ REST (proxied)   ↕ WebSocket
FastAPI (:4040)
  ├─ LangGraph (Gemini via langchain-google-genai)
  ├─ SQLite (aiosqlite) — primary DB
  ├─ Redis (optional) — hot cache
  └─ yfinance — price data (via asyncio.to_thread)
```

### Tech Stack Actually in Use
- **Python 3.x / FastAPI 0.115 / Uvicorn** — backend server
- **LangGraph 0.2+ / LangChain / Gemini** — AI graph (working but no API key)
- **yfinance** — only real data source currently active
- **SQLite + aiosqlite** — only persistent store
- **React 18 + Vite 5 + TypeScript 5** — frontend (vanilla CSS, no UI library)

### Top Observations & Concerns

1. **Three runtime crashes waiting to happen**: `get_all_assets` AttributeError, missing `/trigger-analysis` 404, and `__wrapped__` AttributeError on the client portal endpoint. These should be fixed before any user testing.

2. **AI analysis is entirely non-functional**: The `GEMINI_API_KEY` is empty, and even with a key, the frontend type schema (`recommendations`/`risks`) mismatches the LLM's output schema (`key_risks`/`opportunities`). Both sides need alignment.

3. **No real market data without Upstox**: Without `upstox_client.py`, the ingestor loop produces empty `indices` and `stocks` dicts. Nifty/Sensex in the Dashboard strip will always be blank. The `yfinance`-based `MultiAssetClient` is the only working data source.

4. **Zero tests**: A codebase with async DB calls, LLM invocations, WebSocket broadcast, and JWT auth has no automated coverage at all.

5. **The schema is well-designed but the wiring is incomplete**: The backend DB schema, auth system, and LangGraph structure are all clean and well-thought-out. The gaps are almost exclusively in missing route implementations and a few method name typos — suggesting this is a scaffold that needs its last 20% of connection work done.

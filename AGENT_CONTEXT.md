# WealthWatch 2.0 - Agent Handoff Document

## Project Context
A full architectural revamp of "WealthWatch" to create an agentic web application for wealth managers. WealthWatch 2.0 focuses on:
1. **LangGraph Agentic Backend**: A LangGraph-based market analyst using Gemini.
2. **Real Portfolio Management**: Client deposit and investment tracking via SQLite.
3. **Authentication**: JWT-based auth with separate roles for Wealth Managers (WM) and Clients.
4. **Multi-Asset Support**: `yfinance` for Stocks, Commodities, Crypto, Forex, ETFs.

## Decisions Made
- **Payments**: Manual deposit entry by the Wealth Manager (no payment gateway).
- **Client Portal**: Integrated into the same React app under `/portal` route (not yet built — see TODOs).
- **Old Codebase**: WealthWatch 1.0 committed to GitHub (`origin/main`, commit `09d41e3`).
- **Model Note**: Uses `gemini-2.5-flash` or `gemini-3.6-flash`. Avoid `gemini-2.0-flash` (deprecated).

## Current Implementation State — FULLY SCAFFOLDED

### Backend (all files present and syntax-valid):
| File | Status |
|---|---|
| `config.py` | ✅ Complete (+OPENAI_API_KEY) |
| `main.py` | ✅ Complete (ingestor loop + lifespan) |
| `requirements.txt` | ✅ Complete |
| `auth/jwt_handler.py` | ✅ Complete |
| `auth/dependencies.py` | ✅ Complete |
| `data/database.py` | ✅ Complete (+get_analysis_history()) |
| `data/redis_cache.py` | ✅ Complete |
| `data/multi_asset_client.py` | ✅ Complete |
| `data/upstox_client.py` | ✅ **BUILT** — Real Upstox v2 OAuth + live index data |
| `data/yahoo_fetcher.py` | ✅ **BUILT** — Real yfinance news for 7 Indian tickers |
| `agents/market_graph.py` | ✅ **FIXED** — LLM singleton, aligned schema, error field written |
| `web/routes.py` | ✅ **FIXED** — get_asset_overview bug, client_own_portfolio, realized_pnl, +2 routes |
| `web/ws_manager.py` | ✅ Complete |

> **Note**: `main.py` also attempts to import `data.upstox_client` and `data.yahoo_fetcher` but these are **optional** — they're caught in try/except blocks and the server starts without them.

### Frontend (all files present, TypeScript compiles with 0 errors):
| File | Status |
|---|---|
| `package.json` / `vite.config.ts` / `tsconfig.json` / `index.html` | ✅ Complete |
| `src/main.tsx` | ✅ Complete |
| `src/index.css` | ✅ Complete (full design system + WealthWatch 2.0 extended styles) |
| `src/types/market.ts` | ✅ **NEW** — Created this session |
| `src/api/auth.ts` | ✅ Complete |
| `src/api/clients.ts` | ✅ Complete |
| `src/api/deposits.ts` | ✅ Complete |
| `src/api/investments.ts` | ✅ Complete |
| `src/api/market.ts` | ✅ Complete |
| `src/App.tsx` | ✅ **REWRITTEN** — Login gate + auth-aware routing |
| `src/components/Sidebar.tsx` | ✅ **REWRITTEN** — Auth-aware with logout button |
| `src/components/Login.tsx` | ✅ **NEW** — WM register + login form |
| `src/components/Dashboard.tsx` | ✅ **NEW** — AUM stats + live indices + client table |
| `src/components/Clients.tsx` | ✅ **NEW** — Master/detail client portfolio manager |
| `src/components/Markets.tsx` | ✅ **NEW** — Multi-asset price cards |
| `src/components/Recommendations.tsx` | ✅ **NEW** — LangGraph AI analysis view |
| `src/components/ClientModal.tsx` | ✅ **NEW** — Create/edit client modal |
| `src/components/DepositModal.tsx` | ✅ **NEW** — Record deposit modal |
| `src/components/InvestmentModal.tsx` | ✅ **NEW** — Add/close investment modal |

## How to Run

### Backend
```bash
cd backend
pip install -r requirements.txt
# Create a .env file with:
#   GEMINI_API_KEY=your-key
#   JWT_SECRET=some-secret
python main.py
# Runs on http://localhost:4040
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173 (proxied to backend via vite.config.ts)
```

## Analysis Pass — Bugs Confirmed (2026-09-04)

### Runtime Crashes (will crash on first use)
1. **`AttributeError: get_all_assets`** — `routes.py` calls `_asset_client.get_all_assets()` but `MultiAssetClient` only has `get_asset_overview()`. The Markets page is broken.
2. **`POST /api/market/trigger-analysis` → 404** — Called by `Recommendations.tsx` but never implemented in `routes.py`.
3. **`GET /api/market/analysis/history` → 404** — Same; called in `Recommendations.tsx`, not implemented.

### Schema Mismatch (silent bugs)
4. **LLM output vs. frontend types** — Backend LLM prompt returns `key_risks`, `opportunities`, `recommended_sectors`. Frontend `AnalysisResult` expects `recommendations` and `risks`. Cards in Recommendations page never render.
5. **`client_own_portfolio` uses `__wrapped__`** — `client_portfolio.__wrapped__` doesn't exist; falls back to `_build_portfolio` which hardcodes `realized_pnl: 0`.

### Other Findings
- `GEMINI_API_KEY` is empty in `.env` → LangGraph always produces fallback output
- `MarketState.error` field is declared but never written by any node
- LLM client (`ChatGoogleGenerativeAI`) is re-instantiated on every 60s tick
- No tests exist anywhere
- `wealthwatch.db` WAL files are present (server has run)
- CORS allows `localhost:5000` which matches Vite dev server port ✅

## Completed Features & Decisions (WealthWatch 2.0 + Client Portal & Email Reports)
- **Model Configuration**: Defaulted Gemini model to `gemini-3.6-flash` (`gemini-2.5-flash` / `gemini-2.0-flash` deprecated/unavailable).
- **gemini-3.6-flash response fix**: `response.content` is a list of content blocks, not a string. `market_graph.py` now extracts text from it correctly.
- **Client Authentication & Portal**: Clients added by wealth managers can log in via the "Client Portal" tab, view their personalized portfolio in real-time, and trigger on-demand LangGraph report generation.
- **Gmail SMTP Email Delivery**: Asynchronous HTML report delivery configured using Gmail SMTP (`services/email_service.py`).
- **LangGraph Report Graph**: 3-node LangGraph pipeline (`gather_context` -> `generate_report` -> `format_html`) producing styled executive email reports sent directly to the client's inbox.
- **Vite & FastAPI Setup**: Backend running on `http://localhost:4040`, Vite dev frontend running on `http://localhost:5000` with full API/WebSocket reverse-proxying.
- **Market Loading Fix (2026-09-10)**:
  - Dashboard polls `/api/market/overview` on mount so data appears immediately without waiting 60s for WS tick.
  - After Upstox OAuth callback, `broadcast_once()` fires immediately to push fresh live data to all WS clients.
  - Dashboard shows "Connect to Upstox" button + info banner when `auth_required: true`.
  - WebSocket auto-reconnects on close.
  - Markets page shows slow-load hint after 8s and has 25s per-category timeout. Fetches run in parallel.

## New Frontend Integration (2026-09-10 → 2026-09-11)

### Decision: New Next.js Frontend (`wealth-watch/`)
Replaced the old Vite/React frontend (`frontend/`) with a new Next.js 16 + Tailwind v4 + shadcn frontend located at `wealth-watch/`. Old frontend preserved as backup.

### Key Decisions:
- **Frontend port**: Next.js runs on `localhost:3000` (old Vite was `localhost:5000`)
- **CORS**: Updated `backend/main.py` to allow `localhost:3000` (kept `:5000` for compat)
- **API Proxy**: Added `rewrites()` to `wealth-watch/next.config.mjs` — proxies `/api/*`, `/auth`, `/callback`, `/ws` → `http://localhost:4040`
- **WebSocket**: Cannot be proxied by Next.js rewrites; connects directly to `localhost:4040/ws`
- **Session**: Extended `lib/session.ts` with `token` key (`ww-token`) in localStorage and `getToken()` helper
- **API Layer**: Created `lib/api/` module with typed helpers: `client.ts`, `auth.ts`, `market.ts`, `clients.ts`, `portfolio.ts`, `goals.ts`
- **Mock Data**: Removed fake `instruments[]` and `clients[]` arrays from `lib/mock-data.ts`; kept types and math helpers
- **Goals Feature**: Added `goals` table to SQLite schema + 7 new endpoints in `routes.py` (WM + client portal variants)
- **News Endpoints**: Added `GET /api/news` and `GET /api/news/{symbol}` — uses `NewsFetcher` (yfinance-based)
- **yahoo_fetcher.py bug**: Added missing `_normalise_item()` method + sentiment detection
- **Dashboard**: New manager dashboard page at `/manager/dashboard` with AUM stats, live index strip, AI summary
- **Goals UI**: Full goals CRUD in both WM `client-detail.tsx` and client portal `client/goals.tsx`
- **Report Dialog**: Wired to real `POST /api/client/me/request-report` (falls back gracefully)
- **Upstox Connect**: Banner shown in Market Overview and Dashboard when `auth_required: true`
- **Portfolio History Chart**: Generated deterministically from current value (until real time-series endpoint is built)

### Files Changed:
| File | Change |
|---|---|
| `backend/main.py` | CORS allows `localhost:3000` |
| `backend/data/yahoo_fetcher.py` | Added `_normalise_item()` + sentiment |
| `backend/data/database.py` | Added `goals` table + 4 CRUD methods |
| `backend/web/routes.py` | Added `/api/news`, `/api/news/{symbol}`, 7 goals endpoints |
| `wealth-watch/next.config.mjs` | API proxy rewrites |
| `wealth-watch/lib/session.ts` | JWT token support |
| `wealth-watch/lib/api/*.ts` | New API layer (6 files) |
| `wealth-watch/lib/types.ts` | Shared types + math helpers |
| `wealth-watch/lib/mock-data.ts` | Removed mock data, kept types/math |
| `wealth-watch/components/login-screen.tsx` | Real auth API calls |
| `wealth-watch/components/market/market-overview.tsx` | Real API + WS + Upstox connect |
| `wealth-watch/components/market/instrument-detail.tsx` | Real news from API |
| `wealth-watch/components/clients/clients-workspace.tsx` | Real clients API |
| `wealth-watch/components/clients/client-detail.tsx` | Real portfolio + goals API |
| `wealth-watch/components/client/portfolio.tsx` | Real client portfolio API |
| `wealth-watch/components/client/goals.tsx` | Real goals API |
| `wealth-watch/components/report-dialog.tsx` | Real report API |
| `wealth-watch/components/manager/dashboard.tsx` | NEW: Dashboard component |
| `wealth-watch/app/manager/dashboard/page.tsx` | NEW: Dashboard route |
| `wealth-watch/app/manager/layout.tsx` | Added Dashboard nav item |

### Frontend Path Rename (2026-09-11)
- `wealth-watch/` → renamed to **`frontend/`** (the Next.js app is now the canonical frontend)
- Old Vite/React frontend preserved at **`frontend_old_vite_backup/`** (safe to delete)
- Run command: `cd frontend && npm run dev` → `http://localhost:3000`



## News System Replacement (2026-09-21)
- Replaced Yahoo Finance (yfinance) with a SearXNG + Firecrawl + Gemini LLM pipeline
- **Flow**: SearXNG search ? Firecrawl scrape ? Gemini summarise ? return articles + summary`n- New file: `backend/data/news_fetcher.py` (replaces `yahoo_fetcher.py`)
- Config: `SEARXNG_BASE=https://search.mycilo.app/search`, `FIRECRAWL_BASE=https://firecrawl.mycilo.app`\n- For stock news: searches {SYMBOL} stock market news India, scrapes top 4 URLs, generates 2-3 sentence Gemini summary
- For market news: searches Nifty 50 Sensex Indian stock market news today, scrapes top 5 URLs
- Summary is embedded in articles[0].summary by the pipeline, extracted in route handler
- Old `yahoo_fetcher.py` kept as backup but no longer used

## Report 403 Fix (2026-09-21)
- **Root cause**: `ReportDialog` in `top-nav.tsx` and `client-detail.tsx` was calling `POST /api/client/me/request-report` which uses `require_client`. WM JWT tokens (role=wm) were being sent to this client-only endpoint → 403 Forbidden.
- **Fix**:
  1. Added `POST /api/clients/{client_id}/request-report` in `routes.py` — WM-authenticated, verifies client belongs to WM, reuses `_generate_and_send_report` pipeline.
  2. Updated `report-dialog.tsx`: when `clientId` prop is set → calls WM endpoint; when absent → calls client self-service endpoint.
  3. Removed the global "Report" button from `top-nav.tsx` entirely (WM context, no client selected → button was broken by design). Reports are per-client, triggered from `client-detail.tsx`.
  4. Fixed `report_graph.py` `response.content` list handling (Gemini returns list, not string).


## Knowledge Graph (graphify) — 2026-10-13

- **Built**: Full graphify pipeline run on `d:/Projects/WealthWatch`
- **Outputs**: `graphify-out/graph.json`, `graphify-out/graph.html`, `graphify-out/GRAPH_REPORT.md`
- **Stats**: 683 nodes, 1293 edges, 45 communities (592 AST + 65 semantic)
- **Health**: 78 dangling-endpoint edges (cross-file refs to external libs); 28 collapsed edges — graph is usable
- **God Nodes** (highest betweenness / most connected):
  - `WealthDatabase` (degree 33) — bridges ORM, async config, and REST routes
  - `authJson()` (degree 27) — central to all authenticated frontend API calls
  - `ClientDetail()` (degree 25) — hub of client-facing UI
  - `Delta()`, `cn()` (degree 17) — shared UI utilities
- **Key Communities** (45 total):
  - Market Analysis Pipeline (LangGraph: analyze_node → parse_node → _fallback_analysis)
  - WealthDatabase & ORM (SQLite WAL, aiosqlite, all data models)
  - REST API Routes — split Read vs. Write communities
  - JWT Auth Handler (create_token, hash_password, require_wm/require_client)
  - News Fetcher SearXNG (NewsFetcher replacing yahoo_fetcher)
  - Upstox Integration (OAuth, live index data)
- **To query**: `/graphify query "<question>"` — uses `graphify-out/graph.json`

## Phase 1 Stabilization — 2026-10-15

### Decisions Made
- **Do NOT rewrite**: All fixes are minimal, targeted, and preserve existing behaviour.
- **Two frontends**: `frontend/` = canonical Next.js 16 app. `frontend_old_vite_backup/` = legacy backup, safe to delete.
- **GEMINI_MODEL default**: Changed `gemini-2.0-flash` → `gemini-2.5-flash` (deprecated model caused LangGraph fallbacks).
- **bcrypt ownership**: Added explicit `bcrypt>=4.0.0` to `requirements.txt` because `jwt_handler.py` uses it directly and Python 3.13 broke passlib's bcrypt bridge.
- **Redis TTL**: Increased 90s → 150s so cache doesn't expire between 60s ingestor cycles + ~30s LLM pipeline.
- **Ownership guards**: Added WM ownership checks to `delete_deposit`, `close_investment`, `delete_investment` (any WM could mutate any client's data before).

### Critical Bugs Fixed
1. **`client_me` always returned `{}`** — client JWT has no `email` field; endpoint was looking up by email → fixed to use `int(sub)` + new `get_client_by_id_only()` DB method.
2. **Portfolio N×5s sequential fetches** → converted to `asyncio.gather(...)` parallel.

### Files Changed in Phase 1
| File | Change |
|---|---|
| `backend/config.py` | Default model `gemini-2.0-flash` → `gemini-2.5-flash` |
| `backend/data/database.py` | Added `get_client_by_id_only(client_id)` |
| `backend/data/redis_cache.py` | TTL 90s → 150s |
| `backend/web/routes.py` | 5 targeted fixes |
| `backend/requirements.txt` | Added `bcrypt>=4.0.0` |
| `backend/.env.example` | Added `REDIS_URL`, `SEARXNG_BASE`, `FIRECRAWL_BASE`, `FIRECRAWL_API_KEY` |
| `backend/tests/test_routes.py` | NEW — 9 focused tests |
| `backend/tests/conftest.py` | NEW — pytest config |

### Verification Results (Phase 1 Complete)
- Python syntax: ALL CLEAN (`ast.parse` on all `.py` files)
- TypeScript: `npx tsc --noEmit` exits 0 — zero errors
- Tests: written, cover auth role enforcement, portfolio math, client_me regression

### Phase 2 Recommended Priorities
1. CacheKeys namespace enum (prevent key collisions)
2. Cache per-client portfolio (`portfolio:{client_id}`, 30–60s TTL, invalidate on write)
3. Cache news per symbol (`news:{symbol}`, 10min TTL)
4. Serve market overview HTTP endpoint from Redis broadcast cache

**STOP**: Do not start Phase 2 without explicit user approval.

## Phase 2 Shared Redis Caching — 2026-10-18

### Cache Key Strategy
| Key | TTL | Purpose |
|---|---|---|
| `wealthwatch:news:v1:{exchange}:{symbol}` | 900s (15 min) | Stock news articles + AI summary, shared across all users |
| `wealthwatch:news:v1:market` | 900s (15 min) | Broad Indian market news |
| `wealthwatch:summary:v1:{exchange}:{symbol}:{ANALYSIS_VERSION}` | 900s (15 min) | AI summary only (shared, no client data) |
| `wealthwatch:lock:{key}` | 35s | Distributed lock for stampede prevention |
| `market:snapshot`, `market:broadcast` | 150s | Legacy broadcast cache (unchanged) |

### Lock Strategy
- **setnx + expire** via `redis.set(key, token, nx=True, ex=LOCK_TTL)` — atomic in Redis 2.6.12+
- **Lua CAS delete** for release — only the lock owner can release (prevents cross-request deletion)
- **Waiters** poll every 250ms for up to 5s (20 × 250ms); fall through to independent fetch if wait times out
- **Double-check** after acquiring lock prevents double-work between lock acquisition and cache write

### Decisions Made
- ANALYSIS_VERSION = "1" — bump this string whenever the AI prompt/schema changes to invalidate stale summaries
- Empty article lists and empty summary strings are NEVER cached (failure must not poison the cache)
- Provider exceptions always release the lock via `finally` block
- AI summaries are market-level only — no client name/ID/portfolio data ever enters the shared cache
- Upstox stock articles are fetched live (personalised per watchlist); only the AI summary is cached
- Summary cache cross-pollinates: SearXNG fetch populates both news cache AND summary cache; Upstox summary check reads from same summary cache

### Files Changed in Phase 2
| File | Change |
|---|---|
| `backend/data/redis_cache.py` | Added CacheKeys, `get_news`, `set_news`, `get_summary`, `set_summary`, `acquire_lock`, `release_lock`, `wait_for_lock`, `is_locked` |
| `backend/web/routes.py` | `get_market_news`, `get_stock_news`, `stock_news` — all now cache-aware with stampede protection; added `import asyncio` |
| `backend/tests/test_cache.py` | NEW — 28 tests covering all 9 Phase 2 spec requirements |

### Test Results
- 28 passed, 1 skipped (integration test auto-skips when Redis is not running)
- Stampede test confirms provider called exactly 1 time across 5 concurrent requests

### Phase 3 Candidates (completed in Phase 3)
- Wealth Manager Agentic Stock Analysis workflow with LangGraph
- Client Portfolio Relevance scoring & intelligence dashboard

## Phase 3: Agentic Wealth Manager & Portfolio Intelligence — 2026-10-18

### Architecture & Major Decisions Made
1. **LangGraph Pipeline (`backend/agents/wealth_manager_graph.py`)**:
   - Implemented as a 7-node state graph:
     `validate_input` ➔ `fetch_market_intel` ➔ `fetch_clients` ➔ `calculate_exposures` ➔ `score_clients` ➔ `generate_explanations` ➔ `validate_output`.
   - Node execution uses `await graph.ainvoke(...)` natively within FastAPI async context.
2. **Shared vs Private Separation (Privacy & Security)**:
   - Market summaries and news are fetched/reused via shared Redis cache (`wealthwatch:news:v1:NSE:{symbol}` and `wealthwatch:summary:v1:NSE:{symbol}:1`).
   - Client portfolios are queried using strict `wm_id` database scoping (`WealthDatabase.get_clients(wm_id)`), completely preventing IDOR.
   - Client-specific intelligence and calculations are NEVER cached in the shared Redis cache.
3. **Deterministic Scoring Mechanism (No LLM Arbitrary Ranking)**:
   - Explicit additive scoring scale (0 - 100):
     - Direct stock holding >=5% allocation: +40 pts (HIGH priority)
     - Direct stock holding 1-4.99%: +25 pts (HIGH priority)
     - Direct stock holding <1%: +15 pts (HIGH priority)
     - Target sector exposure >=10%: +20 pts (MODERATE priority)
     - Target sector exposure 5-9.99%: +10 pts (MODERATE priority)
     - Target sector exposure 1-4.99%: +5 pts (LOW priority)
     - Incremental sector exposure for held stocks >=5%: +10 pts
     - Risk profile alignment (Aggressive + Bullish or Conservative + Bearish): +10 pts
     - Zero holdings / missing data: `INSUFFICIENT_DATA` (unscored).
   - Clear classification categories:
     - `HIGH` (>=40 pts): Direct exposure or dominant sector weight
     - `MODERATE` (20-39 pts): Significant sector / indirect link
     - `LOW` (5-19 pts): Minimal connection
     - `INSUFFICIENT_DATA`: No open holdings on file
   - Every client card and output carries explicit disclaimers: High relevance != recommendation to buy/sell; automated trade execution is strictly forbidden.
4. **LLM Orchestration & Prompt Injection Safeguard**:
   - LLM explanations are batched (5 clients per call) only for `HIGH` and `MODERATE` clients.
   - News and headline data are wrapped in read-only market context delimiters.
   - System instructions explicitly command the model to ignore instructions embedded in article text and strictly cite verified facts.
   - If Gemini is unavailable or returns malformed JSON, the pipeline falls back gracefully to deterministic rule-based assessments.
5. **REST API & Route Integration**:
   - `GET /api/wm/stock-analysis/{symbol}?exchange=NSE` added to `backend/web/routes.py`.
   - Protected via `require_wm` dependency. Extracts `wm_id = int(wm["sub"])` from verified JWT.
   - Returns structured JSON containing `market_summary`, `news`, `client_analysis`, and `workflow_metadata`.
6. **Frontend Experience (`frontend/components/wm-analysis/` & `frontend/app/manager/stock-analysis/`)**:
   - Created full Next.js 16 + shadcn dashboard:
     - Interactive symbol search with quick-pick stock buttons.
     - Support for deep-linking via query parameters (`?symbol=XYZ`) with `<Suspense>` wrapper.
     - Market overview card with sentiment chip, AI summary, and Redis cache hit badge.
     - Supporting news section showing title, domain, published date, sentiment, and clickable source links (`target="_blank" rel="noopener noreferrer"`).
     - Category metrics summary banner (High, Moderate, Low, Insufficient counts).
     - Sortable (Score, Priority, Name) and filterable (Categories) client results.
     - Expandable client cards displaying portfolio metrics, sector breakdown, AI assessment, risks, evidence, score breakdown, and compliance disclaimer.
   - Added "Stock Intelligence" navigation item to manager layout.
   - Added "Analyze for Clients" link button on the `InstrumentDetail` market page.

### Files Created in Phase 3
| File | Purpose |
|---|---|
| `backend/agents/wealth_manager_graph.py` | LangGraph workflow orchestrating stock analysis & client relevance |
| `backend/tests/test_wm_analysis.py` | Comprehensive test suite (12 tests covering all requirements) |
| `frontend/lib/api/wm-analysis.ts` | Authenticated API client and TypeScript interfaces |
| `frontend/components/wm-analysis/relevance-badge.tsx` | Category & priority badges |
| `frontend/components/wm-analysis/sentiment-chip.tsx` | Bullish/bearish/neutral sentiment chip |
| `frontend/components/wm-analysis/client-relevance-card.tsx` | Expandable client intelligence card |
| `frontend/components/wm-analysis/stock-analysis-panel.tsx` | Full interactive stock analysis dashboard panel |
| `frontend/app/manager/stock-analysis/page.tsx` | Next.js route for `/manager/stock-analysis` |

### Files Modified in Phase 3
| File | Change |
|---|---|
| `backend/web/routes.py` | Added authenticated `GET /api/wm/stock-analysis/{symbol}` endpoint |
| `frontend/app/manager/layout.tsx` | Added "Stock Intelligence" to manager navigation bar |
| `frontend/components/market/instrument-detail.tsx` | Added "Analyze for Clients" quick-action link button |
| `AGENT_CONTEXT.md` | Documented all Phase 3 decisions and implementation details |

### Verification Results (Phase 3 Complete)
- **Backend Tests**: 12/12 passed in `tests/test_wm_analysis.py` (Direct exposure, sector moderate, no relevant clients, missing portfolio data, multi-manager isolation, invalid symbols, provider failures, malformed LLM fallback, cache window reuse).
- **Python Syntax**: All clean across `wealth_manager_graph.py`, `routes.py`, `test_wm_analysis.py`.
- **Frontend TypeScript**: `npx tsc --noEmit` exited 0 with 0 errors across all Next.js pages and components.

## Upstox OAuth Error UDAPI100068 Resolution (2026-10-23)

### Root Cause
- Upstox error `UDAPI100068` (`Check your 'client_id' and 'redirect_uri'; one or both are incorrect.`) occurred when navigating to `/auth` because `UPSTOX_API_KEY` was still set to the default placeholder `your_upstox_api_key_here` in `backend/.env`.
- Upstox API v2 requires a real App API Key (`client_id`) and an exact match between the App's registered Redirect URL in the Upstox Developer Console and the `redirect_uri` param sent in the request (`http://localhost:4040/callback`).

### Fixes & Guards Added
1. Added `UpstoxClient.is_configured` property in `backend/data/upstox_client.py` to detect placeholder credentials.
2. Updated `/auth` route in `backend/web/routes.py` to intercept unconfigured credentials before redirecting to Upstox, providing an actionable 400 error detailing how to configure the Upstox Developer App.
3. Added `UPSTOX_REDIRECT_URI` to `backend/.env.example` so users know the exact callback URL to configure in the Upstox Developer Console.


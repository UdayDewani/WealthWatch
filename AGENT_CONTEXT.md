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



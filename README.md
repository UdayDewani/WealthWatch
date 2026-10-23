# WealthWatch 💰

**An AI-powered financial market intelligence and wealth management platform for independent wealth managers.**

WealthWatch gives advisors a real-time command centre — live Indian market data, LangGraph-driven AI analysis, full client portfolio tracking, and automated HTML email reports — all in a single self-hosted application.

---

## ✨ Features

### For Wealth Managers
- **Live Market Data** — Nifty 50, Sensex, and individual NSE stocks via Upstox v2 API; falls back to yfinance when Upstox is not connected
- **AI Market Analysis** — LangGraph + Gemini pipeline runs every 60 seconds; streams results to all connected clients via WebSocket
- **Client Portfolio Management** — Track deposits, open/close investments, view realized & unrealized P&L per client
- **Goal Tracking** — Set and monitor financial goals for each client with progress bars
- **Automated Email Reports** — Trigger a per-client LangGraph report (gather context → generate HTML → send via Gmail SMTP) in one click
- **News Intelligence** — SearXNG + Firecrawl + Gemini pipeline fetches and summarises latest stock/market news

### For Clients
- **Self-Service Portal** — Clients log in with their own credentials to view their portfolio, holdings, goals, and P&L in real time
- **On-Demand Reports** — Clients can request their own PDF-quality HTML reports

### Infrastructure
- **Shared Redis Caching** — News and AI summaries are cached for 15 minutes and shared across all users; duplicate LLM/provider calls are prevented by a distributed lock (setnx + Lua CAS)
- **WebSocket Real-Time Updates** — Market data pushed to every connected browser tab simultaneously
- **SQLite WAL** — Lightweight, zero-config database with proper async access

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Next.js 16 Frontend                │
│  (Tailwind v4 · shadcn/ui · TypeScript · Port 3000) │
└────────────────────┬────────────────────────────────┘
                     │  HTTP /api/* (rewrites proxy)
                     │  WebSocket ws://localhost:4040/ws
                     ▼
┌─────────────────────────────────────────────────────┐
│               FastAPI Backend (Port 4040)           │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ JWT Auth    │  │  REST Routes │  │ WebSocket │  │
│  │ WM + Client │  │  (routes.py) │  │ Manager   │  │
│  └─────────────┘  └──────┬───────┘  └─────┬─────┘  │
│                          │                │         │
│  ┌───────────────────────┼────────────────┼───────┐ │
│  │          Data Layer   │                │       │ │
│  │  ┌────────────┐  ┌────┴──────┐  ┌─────┴─────┐ │ │
│  │  │  SQLite    │  │  Redis    │  │  Upstox   │ │ │
│  │  │  (aioSQL)  │  │  Cache    │  │  Client   │ │ │
│  │  └────────────┘  └─────┬─────┘  └───────────┘ │ │
│  │                        │                       │ │
│  │  ┌─────────────────────┴─────────────────────┐ │ │
│  │  │         AI / LLM Layer                    │ │ │
│  │  │  LangGraph Market Graph  ·  Report Graph  │ │ │
│  │  │  NewsFetcher (SearXNG + Firecrawl)        │ │ │
│  │  │  Gemini 2.5 Flash                         │ │ │
│  │  └───────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Description |
|---|---|---|
| FastAPI app + ingestor loop | `backend/main.py` | App lifecycle, 60-second market analysis tick |
| REST + WebSocket routes | `backend/web/routes.py` | All API endpoints (~835 lines) |
| LangGraph market agent | `backend/agents/market_graph.py` | analyze → parse → fallback pipeline |
| LangGraph report agent | `backend/agents/report_graph.py` | gather_context → generate_report → format_html |
| Redis cache | `backend/data/redis_cache.py` | Shared news/summary cache + distributed lock |
| News pipeline | `backend/data/news_fetcher.py` | SearXNG search → Firecrawl scrape → Gemini summary |
| Upstox integration | `backend/data/upstox_client.py` | OAuth v2, live NSE index + stock data |
| Database ORM | `backend/data/database.py` | aiosqlite wrapper, all CRUD operations |
| JWT auth | `backend/auth/jwt_handler.py` | bcrypt passwords, WM + client role tokens |
| Email service | `backend/services/email_service.py` | Async Gmail SMTP report delivery |
| Next.js frontend | `frontend/` | App router, shadcn/ui components |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ (tested on 3.13)
- Node.js 18+ / npm
- Redis (optional — app starts without it, caching disabled)
- A [Gemini API key](https://ai.google.dev/) (optional — AI features disabled without it)

### 1. Backend

```bash
cd backend
cp .env.example .env
# Fill in your credentials in .env (see Configuration below)

pip install -r requirements.txt
python main.py
# → http://localhost:4040
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 3. First use

1. Open `http://localhost:3000`
2. Click **Register** to create a Wealth Manager account
3. Log in and add your first client
4. Record a deposit and add investments
5. (Optional) Connect Upstox via the banner in Dashboard for live NSE data
6. (Optional) Trigger an AI analysis from the Market page

---

## ⚙️ Configuration

Copy `backend/.env.example` to `backend/.env` and set:

```env
# Required
JWT_SECRET=change-me-in-production
GEMINI_API_KEY=your_gemini_api_key

# Email reports (Gmail SMTP)
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# Upstox live data (optional)
UPSTOX_API_KEY=your_upstox_key
UPSTOX_SECRET_KEY=your_upstox_secret

# Redis cache (optional — app works without it)
REDIS_URL=redis://localhost:6379

# News pipeline (optional — self-hosted SearXNG + Firecrawl)
SEARXNG_BASE=https://your-searxng-instance/search
FIRECRAWL_BASE=https://your-firecrawl-instance
FIRECRAWL_API_KEY=your_firecrawl_key
```

All external services are **optional**. The app gracefully degrades:
- No Gemini → AI analysis shows placeholder text
- No Upstox → yfinance prices used for portfolio valuation
- No Redis → caching disabled, every request hits providers directly
- No SearXNG/Firecrawl → news endpoints return empty

---

## 🧠 AI Pipelines

### Market Analysis (every 60 seconds)
```
Upstox/yfinance data + SearXNG news
        ↓
  LangGraph: analyze_node (Gemini prompt)
        ↓
  LangGraph: parse_node (JSON extraction + fallback)
        ↓
  Redis broadcast → WebSocket → all frontend tabs
```

### Client Report (on demand)
```
Client portfolio + goals + market analysis + news
        ↓
  LangGraph: gather_context
        ↓
  LangGraph: generate_report (Gemini — personalized HTML)
        ↓
  LangGraph: format_html
        ↓
  Gmail SMTP → client's inbox
```

### News & Summary Caching
```
Request for /api/news/{symbol}
        ↓
  Redis HIT? → return cached (15-min TTL)
        ↓ MISS
  Acquire distributed lock (setnx)
        ↓
  Double-check cache (another request may have populated it)
        ↓
  SearXNG search → Firecrawl scrape → Gemini summary
        ↓
  Cache result → release lock → return
  (concurrent waiters get cache hit after lock released)
```

---

## 🔑 Authentication

Two JWT roles with separate login flows:

| Role | Login endpoint | Token payload |
|---|---|---|
| Wealth Manager | `POST /api/auth/wm/login` | `{sub, role: "wm", email}` |
| Client | `POST /api/auth/client/login` | `{sub, role: "client", wm_id}` |

- Passwords hashed with bcrypt (Python 3.13 compatible — uses `bcrypt` directly, not passlib bridge)
- Token expiry: 24 hours (configurable via `JWT_EXPIRE_HOURS`)
- WM endpoints reject client tokens and vice versa

---

## 📦 Tech Stack

### Backend
| | |
|---|---|
| Framework | FastAPI 0.115 + uvicorn |
| AI / LLM | LangGraph 0.2 · LangChain · Gemini 2.5 Flash |
| Database | SQLite (aiosqlite) — WAL mode |
| Cache | Redis asyncio client |
| Market data | Upstox v2 API · yfinance 0.2 |
| News | SearXNG · Firecrawl · Gemini |
| Auth | python-jose (JWT) · bcrypt |
| Email | aiosmtplib (Gmail SMTP) |

### Frontend
| | |
|---|---|
| Framework | Next.js 16 (App Router) |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui · lucide-react |
| Language | TypeScript 5 |
| Charts | Custom SVG sparklines |
| Real-time | Native WebSocket |

---

## 🧪 Tests

```bash
cd backend

# Phase 1 — auth, portfolio math, API role enforcement
python -m pytest tests/test_routes.py -v

# Phase 2 — Redis caching, stampede prevention, client isolation
python -m pytest tests/test_cache.py -v

# All tests
python -m pytest tests/ -v
```

Tests run without live credentials — providers and LLM are mocked. The Redis integration test auto-skips when Redis is not running and passes when it is.

---

## 📁 Project Structure

```
WealthWatch/
├── backend/
│   ├── main.py                  # FastAPI app, ingestor loop, lifespan
│   ├── config.py                # Env-var configuration
│   ├── requirements.txt
│   ├── .env.example
│   ├── auth/
│   │   ├── jwt_handler.py       # Token creation, bcrypt hashing
│   │   └── dependencies.py      # require_wm / require_client guards
│   ├── agents/
│   │   ├── market_graph.py      # LangGraph market analysis pipeline
│   │   └── report_graph.py      # LangGraph client report pipeline
│   ├── data/
│   │   ├── database.py          # aiosqlite ORM (all tables + CRUD)
│   │   ├── redis_cache.py       # Shared cache + distributed lock
│   │   ├── news_fetcher.py      # SearXNG + Firecrawl + Gemini news
│   │   ├── upstox_client.py     # Upstox v2 OAuth + live data
│   │   └── multi_asset_client.py# yfinance multi-asset wrapper
│   ├── services/
│   │   └── email_service.py     # Gmail SMTP async email delivery
│   ├── web/
│   │   ├── routes.py            # All REST + WebSocket endpoints
│   │   └── ws_manager.py        # WebSocket connection manager
│   └── tests/
│       ├── test_routes.py       # Auth, portfolio, API role tests
│       └── test_cache.py        # Redis cache + stampede tests
│
├── frontend/                    # Next.js 16 app (canonical)
│   ├── app/
│   │   ├── manager/             # Wealth manager routes
│   │   └── client/              # Client portal routes
│   ├── components/
│   │   ├── manager/             # Dashboard, clients workspace
│   │   ├── clients/             # Client detail, goals
│   │   ├── market/              # Market overview, instrument detail
│   │   └── client/              # Client portal portfolio + goals
│   └── lib/
│       ├── api/                 # Typed fetch helpers
│       ├── session.ts           # JWT token storage
│       └── types.ts             # Shared TypeScript types
│
├── frontend_old_vite_backup/    # Legacy Vite/React frontend (safe to delete)
├── graphify-out/                # Codebase knowledge graph
└── AGENT_CONTEXT.md             # Agent handoff document
```

---

## 🗺 Roadmap

- [ ] Per-client portfolio Redis caching (30–60s TTL, invalidated on writes)
- [ ] Real portfolio time-series endpoint (replace deterministic chart seed)
- [ ] Cache metrics / observability endpoint
- [ ] Upstox real-time WebSocket (replace polling)
- [ ] Multi-currency support
- [ ] Mobile-responsive client portal improvements

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

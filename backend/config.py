from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# Server
PORT = int(os.getenv("PORT", 4040))

# Upstox
UPSTOX_API_KEY    = os.getenv("UPSTOX_API_KEY", "")
UPSTOX_SECRET_KEY = os.getenv("UPSTOX_SECRET_KEY", "")
UPSTOX_REDIRECT   = os.getenv("UPSTOX_REDIRECT_URI", f"http://localhost:{PORT}/callback")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Gemini
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# OpenAI (optional — available for future use)
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

# Gmail — for sending portfolio report emails to clients
GMAIL_SENDER       = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# JWT
JWT_SECRET      = os.getenv("JWT_SECRET", "wealthwatch-super-secret-change-in-prod")
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", 24))

# Data refresh
SNAPSHOT_INTERVAL_HOURS = int(os.getenv("SNAPSHOT_INTERVAL_HOURS", 1))
ANALYSIS_INTERVAL       = int(os.getenv("ANALYSIS_INTERVAL", 60))

# News — SearXNG + Firecrawl pipeline
SEARXNG_BASE    = os.getenv("SEARXNG_BASE",    "https://search.mycilo.app/search")
FIRECRAWL_BASE  = os.getenv("FIRECRAWL_BASE",  "https://firecrawl.mycilo.app")
FIRECRAWL_KEY   = os.getenv("FIRECRAWL_API_KEY", "")   # leave blank for self-hosted


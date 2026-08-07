import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_SECRET_KEY = os.getenv("UPSTOX_SECRET_KEY")
REDIRECT_URI = "http://localhost:4040/callback"
PORT = 4040

# All Gemini API keys for rotation (filter out missing ones)
_all_keys = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
GEMINI_API_KEYS = [k for k in _all_keys if k]

# ---------------------------------------------------------------------------
# Redis configuration
# ---------------------------------------------------------------------------
# Redis is used as the hot cache for market snapshots (TTL 90 s).
# Set REDIS_URL in .env to override (e.g. redis://:password@host:6379/0).
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# SQLite historical snapshot cadence
# ---------------------------------------------------------------------------
# The ingestor loop runs every 60 s but only persists a snapshot to SQLite
# once per SNAPSHOT_INTERVAL_HOURS to avoid excessive storage growth while
# still keeping a rich training dataset.
SNAPSHOT_INTERVAL_HOURS: int = int(os.getenv("SNAPSHOT_INTERVAL_HOURS", "1"))

if not all([GEMINI_API_KEY, UPSTOX_API_KEY, UPSTOX_SECRET_KEY]):
    raise ValueError("Missing one or more required env vars: GEMINI_API_KEY, UPSTOX_API_KEY, UPSTOX_SECRET_KEY")

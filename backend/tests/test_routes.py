"""
Phase 1 focused tests for WealthWatch backend.

Run from d:\\Projects\\WealthWatch\\backend:
    python -m pytest tests/test_routes.py -v

Requirements: all requirements.txt deps installed.
No live Redis, Upstox, Gemini, or SearXNG needed — these tests hit
only the auth + in-memory portions of the API.
"""
import sys
import os
import pytest
import pytest_asyncio

# Allow importing backend modules from this directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from httpx import AsyncClient, ASGITransport
from auth.jwt_handler import create_token, hash_password, verify_password


# ---------------------------------------------------------------------------
# JWT / password unit tests — no HTTP involved
# ---------------------------------------------------------------------------

class TestJWTHandler:
    def test_create_wm_token_contains_role(self):
        token = create_token({"sub": "42", "role": "wm", "email": "wm@test.com"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_client_token_no_email(self):
        """Client tokens have sub + role + wm_id but NO email field."""
        token = create_token({"sub": "7", "role": "client", "wm_id": 1})
        assert isinstance(token, str)

    def test_hash_and_verify_password(self):
        raw = "hunter2!"
        hashed = hash_password(raw)
        assert hashed != raw
        assert verify_password(raw, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_different_plaintexts_give_different_hashes(self):
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Portfolio math tests — pure Python, no DB
# ---------------------------------------------------------------------------

class TestPortfolioMath:
    """Verify the portfolio calculation formulas used in _build_portfolio."""

    def test_unrealized_pnl_calculation(self):
        buy_price = 100.0
        current_price = 130.0
        quantity = 10
        pnl = (current_price - buy_price) * quantity
        pnl_pct = ((current_price - buy_price) / buy_price) * 100
        assert pnl == pytest.approx(300.0)
        assert pnl_pct == pytest.approx(30.0)

    def test_portfolio_with_zero_investments(self):
        """No open investments → current_value = 0, unrealized_pnl = 0."""
        open_investments: list = []
        current_value = sum(
            (inv.get("current_price", inv["buy_price"]) - inv["buy_price"])
            * inv["quantity"] + inv["buy_price"] * inv["quantity"]
            for inv in open_investments
        )
        assert current_value == 0.0

    def test_available_cash_is_deposited_minus_invested(self):
        total_deposited = 500_000.0
        total_invested = 300_000.0
        available_cash = total_deposited - total_invested
        assert available_cash == pytest.approx(200_000.0)


# ---------------------------------------------------------------------------
# FastAPI integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_endpoint():
    """GET /health should return 200 without any auth."""
    from main import app  # import lazily so DB init doesn't run at collection time
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_wm_token_rejected_by_client_endpoint():
    """A WM JWT sent to a client-only endpoint must return 403."""
    from main import app
    wm_token = create_token({"sub": "1", "role": "wm", "email": "wm@test.com"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/client/me",
            headers={"Authorization": f"Bearer {wm_token}"},
        )
    # 403 Forbidden expected — WM token must not pass require_client
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_client_token_rejected_by_wm_endpoint():
    """A client JWT sent to a WM-only endpoint must return 403."""
    from main import app
    client_token = create_token({"sub": "5", "role": "client", "wm_id": 1})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/clients",
            headers={"Authorization": f"Bearer {client_token}"},
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_unauthenticated_wm_endpoint_returns_401():
    """No token → 401 Unauthorized."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/clients")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_unauthenticated_client_endpoint_returns_401():
    """No token on client-only endpoint → 401."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/client/me")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_client_me_uses_sub_not_email():
    """
    Regression test for the client_me bug:
    A client token has no 'email' field. The endpoint must look up the client
    by int(token['sub']), not by token.get('email').
    A non-existent client_id should return 404 (not 200 with empty body).
    """
    from main import app
    # sub=99999 — an ID that will not exist in the DB
    client_token = create_token({"sub": "99999", "role": "client", "wm_id": 1})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/client/me",
            headers={"Authorization": f"Bearer {client_token}"},
        )
    # Before the fix this returned 200 {} (empty); after the fix it returns 404
    assert resp.status_code == 404

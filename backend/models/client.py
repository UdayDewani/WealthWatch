from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class Client(BaseModel):
    """Represents a wealth manager's customer."""

    id: Optional[int] = None
    name: str
    email: str
    phone: str
    pan: str
    risk_profile: str  # "conservative" | "moderate" | "aggressive"
    aum: float         # Assets Under Management in ₹
    joined_date: str   # ISO date string e.g. "2024-01-15"
    notes: str = ""


class ClientCreate(BaseModel):
    """Payload for creating a new client (no id required)."""
    name: str
    email: str
    phone: str
    pan: str
    risk_profile: str
    aum: float
    joined_date: str
    notes: str = ""


class ClientUpdate(BaseModel):
    """Partial-update payload — all fields optional."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pan: Optional[str] = None
    risk_profile: Optional[str] = None
    aum: Optional[float] = None
    joined_date: Optional[str] = None
    notes: Optional[str] = None

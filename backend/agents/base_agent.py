from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    Abstract base class that every specialist agent must inherit from.

    Provides:
    - A ``logger`` scoped to the agent's name
    - ``log_start`` / ``log_done`` timing helpers
    - An abstract ``run()`` method that subclasses must implement
    """

    name: str = "base_agent"

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.name)

    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """
        Execute the agent's primary task.

        Subclasses must accept keyword arguments matching their task contract
        and return a typed result (Pydantic model or plain dict).
        """
        ...

    def log_start(self, task: str) -> float:
        """Log that *task* is starting and return the current monotonic time."""
        self.logger.info("Starting: %s", task)
        return time.monotonic()

    def log_done(self, task: str, start: float) -> None:
        """Log that *task* completed and how long it took."""
        elapsed = time.monotonic() - start
        self.logger.info("Done: %s (%.2fs)", task, elapsed)

"""Token, latency, and estimated cost ledger backed by memory.db."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aspirant.memory.database import open_sqlite

# Approximate per-1M token blended estimates (USD) strictly for user visibility;
# actual billing depends on the user's configured provider plan.
_APPROX_COST_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-4-hydrogen": (0.20, 0.80),
    "gemini-4-argon": (0.50, 2.00),
    "gemini-4-carbon": (1.50, 6.00),
    "gemini-3.5-flash-lite": (0.08, 0.30),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _APPROX_COST_PER_1M.get(model, (0.0, 0.0))
    return round((input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000.0, 6)


class UsageTracker:
    """Persists provider call metrics into SQLite for auditing and cost visibility."""

    def __init__(self, memory_db_path: Path) -> None:
        self.memory_db_path = memory_db_path

    def record(
        self,
        provider: str,
        model: str,
        capability: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        status: str = "ok",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cost = estimate_cost_usd(model, input_tokens, output_tokens)
        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                """
                INSERT INTO provider_usage
                (provider, model, capability, input_tokens, output_tokens, latency_ms, estimated_cost_usd, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    model,
                    capability,
                    max(0, int(input_tokens)),
                    max(0, int(output_tokens)),
                    round(latency_ms, 2),
                    cost,
                    status,
                    now,
                ),
            )

    def summary(self) -> list[dict[str, Any]]:
        with open_sqlite(self.memory_db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    provider,
                    model,
                    COUNT(*) AS calls,
                    SUM(input_tokens) AS total_input_tokens,
                    SUM(output_tokens) AS total_output_tokens,
                    ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
                    ROUND(SUM(estimated_cost_usd), 6) AS total_estimated_cost_usd
                FROM provider_usage
                GROUP BY provider, model
                ORDER BY calls DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

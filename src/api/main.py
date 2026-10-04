"""FastAPI app for Icarus.

The harness exposes only ``GET /health``. The full surface (series,
calendar, baseline, anomaly, methods) is added in later commits.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Icarus", version="0.0.1")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
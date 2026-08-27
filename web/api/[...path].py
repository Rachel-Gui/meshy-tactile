"""Catch-all Vercel entrypoint for FastAPI routes under /api/*."""

from server.app import app

__all__ = ["app"]

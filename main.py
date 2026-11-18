"""ASGI entrypoint used by Python hosting platforms: `uvicorn main:app`."""

from app.main import app

__all__ = ["app"]

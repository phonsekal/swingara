"""Vercel serverless entrypoint.

The @vercel/python runtime picks up the ASGI `app` object from this file.
"""
from app.main import app  # noqa: F401
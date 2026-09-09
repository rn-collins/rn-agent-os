"""Vercel entry point for the rn-agent-os API.

The engine is a seven-container Docker stack; this deploys only the part that needs
none of it. The Disclosure + Claims agent grades text deterministically and returns
JSON directly, so /health and that endpoint run with no database, no model key and no
Ollama. Everything requiring Postgres, the local model, n8n or Metabase stays
self-hosted, and the endpoints say so rather than pretending.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.api.main import app  # noqa: E402,F401

# Vercel's Python runtime serves the ASGI callable exported as `app`.

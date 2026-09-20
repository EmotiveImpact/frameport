"""Vercel ASGI entrypoint for the Frameport studio.

Vercel can host the FastAPI shell/API, but the Chromium conversion worker is
not treated as production-ready serverless compute. Local/worker deployments
remain the supported path for actual conversion jobs.
"""
from pathlib import Path
import os

# Vercel may define optional environment variables as empty strings. Normalise
# settings that are parsed as integers before constructing the application.
if not os.environ.get("FRAMEPORT_RETENTION_DAYS"):
    os.environ["FRAMEPORT_RETENTION_DAYS"] = "7"

from frameport.app import create_app
from frameport.config import Settings

app = create_app(
    Settings(
        data=Path("/tmp/frameport"),
        api_key=os.environ.get("FRAMEPORT_API_KEY", ""),
        allowed_hosts=("*",),
    )
)

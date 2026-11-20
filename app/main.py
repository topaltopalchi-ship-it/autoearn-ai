from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(
    title="AutoEarn AI",
    description="Private, Supabase-backed opportunity and reward workspace.",
    version="0.2.0",
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AutoEarn AI", "version": app.version}


# Serve the static site at the root so relative asset URLs in index.html resolve.
# Register this mount after API routes so it cannot shadow /api/health.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


# All user data is accessed directly through Supabase Auth + RLS in the browser.
# No unauthenticated SQLite CRUD API is exposed by this server.

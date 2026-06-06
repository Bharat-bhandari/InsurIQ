"""Backend entrypoint. The FastAPI app (with /health and /ask) lives in
`src.api.app`; this module just re-exports it so `uvicorn main:app` keeps
working and adds the local dev runner."""

import os

import uvicorn

from src.api.app import app  # noqa: F401  (re-exported for `uvicorn main:app`)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8082"))
    reload_mode = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run("main:app", host=host, port=port, reload=reload_mode)

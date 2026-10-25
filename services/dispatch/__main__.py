"""Start only Dispatch, using its service-owned environment settings."""

import uvicorn

from .src.config import get_settings


if __name__ == "__main__":
    uvicorn.run("services.dispatch.src.api:app", host="127.0.0.1", port=get_settings().dispatch_port)

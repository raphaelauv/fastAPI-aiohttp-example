"""The shared aiohttp session: how endpoints and services get it, and a small helper to call upstream."""

from typing import Annotated, Any

import aiohttp
from fastapi import Depends, HTTPException, Request

UPSTREAM_BASE_URL = "http://localhost:8080"
UPSTREAM_PATH = "/test"


def get_http_client(request: Request) -> aiohttp.ClientSession:
    """Return the session opened by the app lifespan (override this in tests)."""
    client: aiohttp.ClientSession = request.state.http_client
    return client


HTTPClient = Annotated[aiohttp.ClientSession, Depends(get_http_client)]


async def fetch_json(client: aiohttp.ClientSession, path: str) -> dict[str, Any]:
    """POST to an upstream path (relative to the session base_url) and return its JSON body.

    Upstream failures (connection errors, timeouts, non-2xx answers, invalid JSON) become a 502.
    """
    try:
        async with client.post(path) as response:
            response.raise_for_status()
            result: dict[str, Any] = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e or type(e).__name__}") from e
    return result

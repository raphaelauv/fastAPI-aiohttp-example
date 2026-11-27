import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from socket import AF_INET
from typing import Annotated, Any, TypedDict

import aiohttp
from fastapi import FastAPI, Query, Request, Response
from fastapi.logger import logger

from fastAPI_aiohttp.http_client import UPSTREAM_BASE_URL, UPSTREAM_PATH, HTTPClient, fetch_json
from fastAPI_aiohttp.services import Report

SIZE_POOL_AIOHTTP = 100


class State(TypedDict):
    http_client: aiohttp.ClientSession


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[State]:
    """Open one shared ClientSession at startup and close it at shutdown."""
    timeout = aiohttp.ClientTimeout(total=2)
    connector = aiohttp.TCPConnector(family=AF_INET, limit_per_host=SIZE_POOL_AIOHTTP)
    async with aiohttp.ClientSession(UPSTREAM_BASE_URL, timeout=timeout, connector=connector) as client:
        logger.info("HTTP client opened")
        yield {"http_client": client}
    logger.info("HTTP client closed")


app = FastAPI(docs_url="/", lifespan=lifespan)


@app.get("/endpoint")
async def endpoint(client: HTTPClient) -> dict[str, Any]:
    return await fetch_json(client, UPSTREAM_PATH)


@app.get("/endpoint_multi")
async def endpoint_multi(client: HTTPClient) -> dict[str, int]:
    # both upstream calls run concurrently
    first, second = await asyncio.gather(fetch_json(client, UPSTREAM_PATH), fetch_json(client, UPSTREAM_PATH))
    return {"success": first["success"] + second["success"]}


@app.get("/endpoint_complex_codebase")
async def endpoint_complex_codebase(report: Report, calls: Annotated[int, Query(ge=1, le=10)] = 3) -> dict[str, int]:
    # the endpoint asks for a service, not for the HTTP client (see services.py)
    return await report.build_report(calls)


@app.post("/endpoint_stream")
async def endpoint_stream(request: Request) -> Response:
    body = bytearray(b"RST")
    async for chunk in request.stream():
        body += chunk
    return Response(bytes(body), media_type="text/plain")


if __name__ == "__main__":  # local dev
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

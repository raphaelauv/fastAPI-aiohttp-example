from collections.abc import AsyncIterator

import aiohttp
import httpx2
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import HTTPException

from fastAPI_aiohttp.fastAPI import app, lifespan
from fastAPI_aiohttp.http_client import UPSTREAM_PATH, fetch_json, get_http_client


class FakeUpstream:
    """A real aiohttp server answering queued responses on UPSTREAM_PATH."""

    def __init__(self) -> None:
        self._responses: list[web.Response] = []
        self.session: aiohttp.ClientSession

    def add_response(self, status: int = 200, json: object = None) -> None:
        self._responses.append(web.json_response(json, status=status))

    async def handler(self, _request: web.Request) -> web.Response:
        if not self._responses:
            return web.Response(status=599, text="No response registered")
        return self._responses.pop(0)

    def assert_all_responses_used(self) -> None:
        assert not self._responses, f"{len(self._responses)} registered responses were not requested"


@pytest.fixture
async def upstream() -> AsyncIterator[FakeUpstream]:
    fake = FakeUpstream()
    upstream_app = web.Application()
    upstream_app.router.add_post(UPSTREAM_PATH, fake.handler)
    async with TestServer(upstream_app) as server:
        async with aiohttp.ClientSession(f"http://{server.host}:{server.port}") as session:
            fake.session = session
            yield fake
    fake.assert_all_responses_used()


@pytest.fixture
async def client_fastAPI(upstream: FakeUpstream) -> AsyncIterator[httpx2.AsyncClient]:
    """Calls the app in-process; its endpoints receive a session pointed at the fake upstream."""
    app.dependency_overrides[get_http_client] = lambda: upstream.session
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


async def test_fetch_json(upstream: FakeUpstream) -> None:
    upstream.add_response(json={"result": 2})
    assert await fetch_json(upstream.session, UPSTREAM_PATH) == {"result": 2}


async def test_fetch_json_upstream_error(upstream: FakeUpstream) -> None:
    upstream.add_response(status=500)
    with pytest.raises(HTTPException) as exc_info:
        await fetch_json(upstream.session, UPSTREAM_PATH)
    assert exc_info.value.status_code == 502


async def test_endpoint(upstream: FakeUpstream, client_fastAPI: httpx2.AsyncClient) -> None:
    upstream.add_response(json={"success": 1})
    assert (await client_fastAPI.get("/endpoint")).json() == {"success": 1}


async def test_endpoint_upstream_error(upstream: FakeUpstream, client_fastAPI: httpx2.AsyncClient) -> None:
    upstream.add_response(status=503)
    assert (await client_fastAPI.get("/endpoint")).status_code == 502


async def test_endpoint_multi(upstream: FakeUpstream, client_fastAPI: httpx2.AsyncClient) -> None:
    upstream.add_response(json={"success": 1})
    upstream.add_response(json={"success": 2})
    assert (await client_fastAPI.get("/endpoint_multi")).json() == {"success": 3}


async def test_endpoint_complex_codebase(upstream: FakeUpstream, client_fastAPI: httpx2.AsyncClient) -> None:
    # the single get_http_client override reaches the session deep inside ReportService -> UpstreamAPI
    for value in (1, 2, 3):
        upstream.add_response(json={"success": value})
    assert (await client_fastAPI.get("/endpoint_complex_codebase")).json() == {"calls": 3, "success": 6}


async def test_endpoint_complex_codebase_upstream_error(upstream: FakeUpstream, client_fastAPI: httpx2.AsyncClient) -> None:
    upstream.add_response(status=503)
    assert (await client_fastAPI.get("/endpoint_complex_codebase", params={"calls": 1})).status_code == 502


async def test_endpoint_complex_codebase_calls_bounds(client_fastAPI: httpx2.AsyncClient) -> None:
    assert (await client_fastAPI.get("/endpoint_complex_codebase", params={"calls": 0})).status_code == 422
    assert (await client_fastAPI.get("/endpoint_complex_codebase", params={"calls": 11})).status_code == 422


async def test_endpoint_stream(client_fastAPI: httpx2.AsyncClient) -> None:
    data = b"TOTO" * 10000
    response = await client_fastAPI.post("/endpoint_stream", content=data)
    assert response.content == b"RST" + data


async def test_lifespan_opens_and_closes_client() -> None:
    async with lifespan(app) as state:
        client = state["http_client"]
        assert not client.closed
    assert client.closed

"""Using the shared client deep in a codebase, without passing it through every function call.

Each class receives what it needs once, in its constructor, and FastAPI builds the whole chain
for every request: endpoint -> ReportService -> UpstreamAPI -> aiohttp session.
Only UpstreamAPI knows about the HTTP client; the endpoint only knows about ReportService.
"""

import asyncio
from typing import Annotated

from fastapi import Depends

from fastAPI_aiohttp.http_client import UPSTREAM_PATH, HTTPClient, fetch_json


class UpstreamAPI:
    """Low level: the only class that talks HTTP."""

    def __init__(self, client: HTTPClient) -> None:
        self.client = client

    async def get_success(self) -> int:
        data = await fetch_json(self.client, UPSTREAM_PATH)
        return int(data["success"])


class ReportService:
    """High level: business logic, several calls deep, never sees the HTTP client."""

    def __init__(self, upstream: Annotated[UpstreamAPI, Depends()]) -> None:
        self.upstream = upstream

    async def build_report(self, calls: int) -> dict[str, int]:
        values = await self._collect(calls)
        return self._summarize(values)

    async def _collect(self, calls: int) -> list[int]:
        # concurrent upstream calls, still without passing any client around
        return list(await asyncio.gather(*(self.upstream.get_success() for _ in range(calls))))

    @staticmethod
    def _summarize(values: list[int]) -> dict[str, int]:
        # plain logic: needs data, not the client
        return {"calls": len(values), "success": sum(values)}


Report = Annotated[ReportService, Depends()]

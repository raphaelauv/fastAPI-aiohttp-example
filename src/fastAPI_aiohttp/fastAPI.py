import json
import asyncio
from collections.abc import Coroutine
from socket import AF_INET
from typing import List, Tuple

import aiohttp
from aioresponses import aioresponses
from fastapi import FastAPI
from fastapi.logger import logger
import uvicorn

fastAPI_logger = logger  # convenient name

SIZE_POOL_AIOHTTP = 100


class SingletonAiohttp:
    sem: asyncio.Semaphore = None
    aiohttp_client: aiohttp.ClientSession = None

    @classmethod
    def get_aiohttp_client(cls) -> aiohttp.ClientSession:
        if cls.aiohttp_client is None:
            timeout = aiohttp.ClientTimeout(total=2)
            connector = aiohttp.TCPConnector(family=AF_INET, limit_per_host=SIZE_POOL_AIOHTTP)
            cls.aiohttp_client = aiohttp.ClientSession(timeout=timeout, connector=connector)

        return cls.aiohttp_client

    @classmethod
    async def close_aiohttp_client(cls):
        if cls.aiohttp_client:
            await cls.aiohttp_client.close()
            cls.aiohttp_client = None

    @classmethod
    async def query_url(cls, url: str):
        client = cls.get_aiohttp_client()

        try:
            async with client.post(url) as response:
                if response.status != 200:
                    return {"ERROR OCCURED" + str(await response.text())}

                json_result = await response.json()
        except Exception as e:
            return {"ERROR": e}

        return json_result


async def on_start_up():
    fastAPI_logger.info("on_start_up")
    SingletonAiohttp.get_aiohttp_client()


async def on_shutdown():
    fastAPI_logger.info("on_shutdown")
    await SingletonAiohttp.close_aiohttp_client()


app = FastAPI(docs_url="/", on_startup=[on_start_up], on_shutdown=[on_shutdown])


@app.get('/endpoint')
async def endpoint():
    url = "http://localhost:8080/test"

    with aioresponses() as mock_server:  # mock answer , remove in real
        mock_server.post(url=url, status=200, body=json.dumps({"succes": 1}))

        rst = await SingletonAiohttp.query_url(url)
    return rst


@app.get('/endpoint_multi')
async def endpoint_mutli():
    url = "http://localhost:8080/test"

    with aioresponses() as mock_server:  # mock answer , remove in real
        mock_server.post(url=url, status=200, body=json.dumps({"succes": 1}))
        mock_server.post(url=url, status=200, body=json.dumps({"succes": 2}))

        async_calls: List[Coroutine] = list()  # store all async operations

        async_calls.append(SingletonAiohttp.query_url(url))
        async_calls.append(SingletonAiohttp.query_url(url))

        all_results: List[Tuple] = await asyncio.gather(*async_calls)  # wait for all async operations
    return {'succes': sum([x['succes'] for x in all_results])}


if __name__ == '__main__':  # local dev

    uvicorn.run(app, host="0.0.0.0", port=8000)

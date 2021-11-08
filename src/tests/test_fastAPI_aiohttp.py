import json

import requests
from aioresponses import aioresponses
from fastapi.testclient import TestClient
import pytest

from fastAPI_aiohttp.fastAPI import app, SingletonAiohttp

url = "test/toto"


@pytest.fixture
def client_aio():
    with aioresponses() as m:
        m.post(url=url,
               status=200,
               body=json.dumps({"result": 2}))
        yield m


@pytest.fixture
def client_fastAPI():
    return TestClient(app=app)


@pytest.mark.asyncio
async def test_query_url(client_aio):
    rst = await SingletonAiohttp.query_url(url)
    assert rst == {"result": 2}


def test_endpoint(client_fastAPI):
    result: requests.Response = client_fastAPI.get(url='/endpoint/')
    assert result is not None

    result_json = result.json()
    assert result_json == {'succes': 1}


def test_endpoint_multi(client_fastAPI):
    result: requests.Response = client_fastAPI.get(url='/endpoint_multi/')
    assert result is not None

    result_json = result.json()
    assert result_json == {'succes': 3}


def test_endpoint_stream(client_fastAPI):
    data = b'TOTO' * 10000

    result: requests.models.Response = client_fastAPI.request('POST', url='/endpoint_stream/', data=data, stream=True)
    assert result is not None
    rst = result.content
    assert rst == b'RST' + data

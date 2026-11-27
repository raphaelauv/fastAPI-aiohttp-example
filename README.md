![Python](https://github.com/raphaelauv/fastAPI-aiohttp-example/workflows/Python/badge.svg?branch=master)

# Full example of [FastAPI](https://github.com/tiangolo/fastapi) with an [aiohttp](https://github.com/aio-libs/aiohttp) client

### This is an example with FastAPI, but you can use this logic with any async ( ASGI ) web framework

### [EXAMPLE FOR HTTPX2](https://github.com/raphaelauv/fastAPI-httpx2-example/)

#### Implemented logic :

- Open one shared `ClientSession` at FastAPI startup and close it at shutdown, in a FastAPI `lifespan`
- Hand the session to endpoints through the lifespan state and `Depends`
- Turn upstream failures (connection errors, timeouts, non-2xx answers) into a `502`
- Run several upstream calls concurrently with `asyncio.gather`
- Use the session deep in a codebase without passing it through every function (`/endpoint_complex_codebase`)

#### Code layout

- [`fastAPI.py`](src/fastAPI_aiohttp/fastAPI.py): the app, its `lifespan` and the endpoints
- [`http_client.py`](src/fastAPI_aiohttp/http_client.py): the `HTTPClient` dependency and the `fetch_json` helper
- [`services.py`](src/fastAPI_aiohttp/services.py): service classes used by `/endpoint_complex_codebase`

#### Using the session deep in your code

`/endpoint` and `/endpoint_multi` receive the session with `Depends` and pass it as an argument.
That's fine for one level, but in a real codebase the HTTP call is often several functions deep.

`/endpoint_complex_codebase` shows how to avoid passing the session through every call:
each class receives what it needs **once, in its constructor**, and FastAPI builds the chain for every request.

```text
endpoint_complex_codebase(report: Report)       # only asks for the service
  -> ReportService(upstream: UpstreamAPI)       # business logic, never sees the session
       -> UpstreamAPI(client: HTTPClient)       # the only class that talks HTTP
            -> aiohttp.ClientSession            # opened and closed by the lifespan
```

Inside the classes, methods use `self.upstream` / `self.client`, so no call takes the session as an argument.

| Where the session lives | You write | Cost |
|---|---|---|
| Function arguments | `f(client, ...)` at every level | Verbose once the calls get deep |
| An object (this repo's services) | One `Depends` per endpoint, `self.client` inside | Needs a class |
| A module global set by the lifespan | `get_client()` anywhere | Hidden dependency; tests must patch the global |

## Run

```bash
uv sync --all-extras
uv run python src/fastAPI_aiohttp/fastAPI.py
```

## Tests

```bash
uv run pytest
```

The tests start a fake upstream server with aiohttp's own
[`TestServer`](https://docs.aiohttp.org/en/stable/testing.html), and point the app's session at it
with `app.dependency_overrides` (the session uses a `base_url`, so only the host changes).
One override reaches the session everywhere, including deep inside `UpstreamAPI`.

[aioresponses](https://github.com/pnuckowski/aioresponses) is not used: it is broken with aiohttp 3.14
([#289](https://github.com/pnuckowski/aioresponses/issues/289)).

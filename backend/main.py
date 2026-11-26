
"""AEGIS FastAPI application with live Coinbase market data.

Coinbase BTC-USD prices are real reference data. All AEGIS orders,
matching, trades, and executions remain simulated.
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import sys
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import certifi
import httpx
import websockets
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "src"
FRONTEND_FILE = PROJECT_ROOT / "frontend" / "index.html"
BENCHMARK_FRONTEND_FILE = PROJECT_ROOT / "frontend" / "benchmark.html"
BENCHMARK_REPORT = PROJECT_ROOT / "benchmarks" / "report.json"
CPP_EXECUTABLE = PROJECT_ROOT / "build" / "aegis_engine"

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from aegis.differential import compare_engines, run_python_engine  # noqa: E402
from aegis.generator import generate_events  # noqa: E402
from aegis.runner import run_events  # noqa: E402

APP_VERSION = "1.3.0"
COINBASE_REST_URL = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
MARKET_TIMEOUT_SECONDS = 8.0
MARKET_STALE_AFTER_SECONDS = 30.0
MAX_EVENTS = 1_000
RECONNECT_MIN_SECONDS = 1.0
RECONNECT_MAX_SECONDS = 30.0

latest_market_data: dict[str, Any] | None = None

feed_status: dict[str, Any] = {
    "status": "starting",
    "source": "Coinbase Exchange WebSocket",
    "last_message_at": None,
    "last_error": None,
    "reconnect_attempts": 0,
}

market_clients: set[WebSocket] = set()


class SimulationRequest(BaseModel):
    """Bounded request model for a deterministic simulation run."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=42, ge=0, le=(2**32) - 1)
    event_count: int = Field(default=100, ge=1, le=MAX_EVENTS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def market_snapshot_is_fresh() -> bool:
    if latest_market_data is None:
        return False

    received = latest_market_data.get("received_at_epoch")

    return isinstance(received, (int, float)) and (
        datetime.now(timezone.utc).timestamp() - received
        <= MARKET_STALE_AFTER_SECONDS
    )


async def broadcast_market_update(payload: dict[str, Any]) -> None:
    """Send market updates to connected browser clients."""

    if not market_clients:
        return

    dead: list[WebSocket] = []
    message = json.dumps(payload, separators=(",", ":"))

    for client in tuple(market_clients):
        try:
            await client.send_text(message)
        except Exception:
            dead.append(client)

    for client in dead:
        market_clients.discard(client)


async def coinbase_feed_loop() -> None:
    """Maintain a reconnecting public Coinbase ticker connection."""

    global latest_market_data

    backoff = RECONNECT_MIN_SECONDS

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    while True:
        feed_status["status"] = "connecting"

        try:
            async with websockets.connect(
                COINBASE_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=1_000_000,
            ) as socket:

                await socket.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": ["BTC-USD"],
                    "channels": ["ticker", "heartbeat"],
                }))

                feed_status["status"] = "connected"
                feed_status["last_error"] = None
                feed_status["reconnect_attempts"] = 0

                backoff = RECONNECT_MIN_SECONDS

                async for raw_message in socket:
                    try:
                        message = json.loads(raw_message)
                    except (json.JSONDecodeError, TypeError):
                        continue

                    message_type = message.get("type")

                    if (
                        message_type == "ticker"
                        and message.get("product_id") == "BTC-USD"
                    ):
                        try:
                            price = float(message["price"])

                            if not (
                                price > 0
                                and price < float("inf")
                            ):
                                continue

                        except (KeyError, TypeError, ValueError):
                            continue

                        received_at = utc_now()

                        latest_market_data = {
                            "symbol": "BTC-USD",
                            "price": price,
                            "currency": "USD",
                            "source": "Coinbase Exchange WebSocket",
                            "is_live": True,
                            "feed_type": "WEBSOCKET",
                            "exchange_time": message.get("time"),
                            "received_at": received_at,
                            "received_at_epoch": (
                                datetime.now(timezone.utc).timestamp()
                            ),
                            "sequence": message.get("sequence"),
                            "best_bid": message.get("best_bid"),
                            "best_ask": message.get("best_ask"),
                        }

                        feed_status["status"] = "live"
                        feed_status["last_message_at"] = received_at
                        feed_status["last_error"] = None

                        await broadcast_market_update({
                            "type": "market_update",
                            "market": {
                                key: value
                                for key, value in latest_market_data.items()
                                if key != "received_at_epoch"
                            },
                            "feed": dict(feed_status),
                        })

                    elif message_type == "heartbeat":
                        feed_status["last_message_at"] = utc_now()

                        if feed_status["status"] != "live":
                            feed_status["status"] = "connected"

        except asyncio.CancelledError:
            raise

        except Exception as error:
            feed_status["status"] = "reconnecting"
            feed_status["last_error"] = str(error)[:300]

            feed_status["reconnect_attempts"] = int(
                feed_status.get("reconnect_attempts", 0)
            ) + 1

        await asyncio.sleep(backoff)

        backoff = min(
            backoff * 2,
            RECONNECT_MAX_SECONDS,
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    feed_task = asyncio.create_task(coinbase_feed_loop())

    try:
        yield

    finally:
        feed_task.cancel()

        with suppress(asyncio.CancelledError):
            await feed_task


app = FastAPI(
    title="AEGIS API",
    description=(
        "A deterministic exchange simulator and adversarial verification "
        "system. Coinbase market prices are real reference data; all exchange "
        "activity generated by AEGIS is simulated."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)


async def fetch_market_rest_fallback() -> dict[str, Any]:
    """Fetch a Coinbase REST reference when the WebSocket has no fresh tick."""

    try:
        timeout = httpx.Timeout(MARKET_TIMEOUT_SECONDS)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                COINBASE_REST_URL,
                headers={"Accept": "application/json"},
            )

            response.raise_for_status()
            payload = response.json()

        amount = float(payload["data"]["amount"])

        if not (
            amount > 0
            and amount < float("inf")
        ):
            raise ValueError(
                "Market provider returned an invalid price"
            )

        return {
            "symbol": "BTC-USD",
            "price": amount,
            "currency": "USD",
            "source": "Coinbase REST fallback",
            "is_live": True,
            "feed_type": "REST_FALLBACK",
            "exchange_time": None,
            "received_at": utc_now(),
            "best_bid": None,
            "best_ask": None,
        }

    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Market price unavailable. The Coinbase WebSocket has no "
                "fresh ticker and the REST fallback failed."
            ),
        ) from error


async def get_market_reference() -> dict[str, Any]:
    if (
        market_snapshot_is_fresh()
        and latest_market_data is not None
    ):
        return {
            key: value
            for key, value in latest_market_data.items()
            if key != "received_at_epoch"
        }

    return await fetch_market_rest_fallback()


def _build_simulation_response(
    seed: int,
    event_count: int,
    market_data: dict[str, Any],
) -> dict[str, Any]:
    """Run all engines and invariant checks outside the async event loop."""

    if not CPP_EXECUTABLE.is_file():
        raise RuntimeError(
            "C++ engine executable not found. Build cpp/src/main.cpp and "
            "cpp/src/exchange.cpp into build/aegis_engine first."
        )

    market_price_cents = round(
        float(market_data["price"]) * 100
    )

    events = generate_events(
        seed=seed,
        event_count=event_count,
    )

    for event in events:
        if event["type"] == "LIMIT":
            offset_cents = (event["price"] - 100) * 100
            event["price"] = market_price_cents + offset_cents

    comparison = compare_engines(
        events,
        executable=str(CPP_EXECUTABLE),
    )

    python_results = run_python_engine(events)
    invariant_report = run_events(events)

    return {
        "market": market_data,
        "simulation": {
            "seed": seed,
            "event_count": len(events),
            "execution_type": "SIMULATED",
            "price_unit": "USD cents",
            "events": events,
            "results": python_results,
        },
        "verification": comparison,
        "invariants": {
            "valid": invariant_report.valid,
            "violations": invariant_report.violations,
        },
    }


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    if not FRONTEND_FILE.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend file not found",
        )

    return FileResponse(FRONTEND_FILE)


@app.get("/benchmark", include_in_schema=False)
def benchmark_dashboard() -> FileResponse:
    if not BENCHMARK_FRONTEND_FILE.is_file():
        raise HTTPException(
            status_code=404,
            detail="Benchmark dashboard file not found",
        )

    return FileResponse(BENCHMARK_FRONTEND_FILE)


@app.get("/health")
def health() -> dict[str, Any]:
    cpp_available = CPP_EXECUTABLE.is_file()

    return {
        "status": "healthy" if cpp_available else "degraded",
        "version": APP_VERSION,
        "python_engine": True,
        "reference_engine": True,
        "cpp_engine": cpp_available,
        "benchmark_report": BENCHMARK_REPORT.is_file(),
        "benchmark_dashboard": BENCHMARK_FRONTEND_FILE.is_file(),
        "market_data": (
            "Coinbase Exchange WebSocket ticker with REST fallback"
        ),
        "market_feed_status": feed_status["status"],
        "market_feed_last_message_at": feed_status["last_message_at"],
        "market_feed_reconnect_attempts": (
            feed_status["reconnect_attempts"]
        ),
        "execution": "simulated only",
        "max_events_per_run": MAX_EVENTS,
    }


@app.get("/benchmark/report")
def benchmark_report() -> dict[str, Any]:
    """Return the locally generated, recorded benchmark report."""

    if not BENCHMARK_REPORT.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Benchmark report not found. Run "
                "benchmarks/benchmark.py and include benchmarks/report.json "
                "in the deployment."
            ),
        )

    try:
        with BENCHMARK_REPORT.open("r", encoding="utf-8") as report_file:
            report = json.load(report_file)

    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500,
            detail="Benchmark report could not be read.",
        ) from error

    if not isinstance(report, dict):
        raise HTTPException(
            status_code=500,
            detail="Benchmark report has an invalid format.",
        )

    return report


@app.get("/market")
async def market() -> dict[str, Any]:
    return await get_market_reference()


@app.get("/market/status")
def market_status() -> dict[str, Any]:
    return {
        "feed": dict(feed_status),
        "has_price": latest_market_data is not None,
        "price_is_fresh": market_snapshot_is_fresh(),
        "latest_market": (
            {
                key: value
                for key, value in latest_market_data.items()
                if key != "received_at_epoch"
            }
            if latest_market_data is not None
            else None
        ),
    }


@app.websocket("/ws/market")
async def market_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    market_clients.add(websocket)

    try:
        await websocket.send_json({
            "type": "connection",
            "feed": dict(feed_status),
            "market": (
                {
                    key: value
                    for key, value in latest_market_data.items()
                    if key != "received_at_epoch"
                }
                if latest_market_data is not None
                else None
            ),
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        market_clients.discard(websocket)


@app.post("/simulate")
async def simulate(
    request: SimulationRequest,
) -> dict[str, Any]:
    market_data = await get_market_reference()

    try:
        return await run_in_threadpool(
            _build_simulation_response,
            request.seed,
            request.event_count,
            market_data,
        )

    except (OSError, RuntimeError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {error}",
        ) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )

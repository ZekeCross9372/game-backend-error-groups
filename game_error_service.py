"""HTTP service that groups game backend failures by operational cause."""

from __future__ import annotations

import hashlib
import traceback
from enum import Enum
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from infrai_client import InfraiClient, InfraiError, InfraiTransportError


class ErrorSurface(str, Enum):
    PLAYER_ASSET = "player_asset"
    LIVE_EVENT = "live_event"
    MODERATION_QUEUE = "moderation_queue"


class GameBackendError(BaseModel):
    surface: ErrorSurface
    operation: str = Field(min_length=1, max_length=80)
    error_type: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    traceback: str = Field(min_length=1)
    player_id: str | None = None
    asset_id: str | None = None
    live_event_id: str | None = None
    moderation_queue: str | None = None


class CaptureResult(BaseModel):
    status: Literal["captured"]
    group_key: str
    event: dict[str, Any]


def group_key(error: GameBackendError) -> str:
    """Keep high-cardinality entity IDs out of the issue identity."""
    return f"{error.surface.value}:{error.operation}:{error.error_type}"


def capture_game_error(error: GameBackendError, client: InfraiClient) -> CaptureResult:
    key = group_key(error)
    occurrence = "|".join(
        value
        for value in (
            error.player_id,
            error.asset_id,
            error.live_event_id,
            error.moderation_queue,
            error.message,
        )
        if value
    )
    request_id = hashlib.sha256(f"{key}|{occurrence}".encode()).hexdigest()
    event = client.capture_error(
        {
            "title": f"{error.surface.value}/{error.operation} failed",
            "message": error.message,
            "level": "error",
            "fingerprint": [key],
            "exception": error.traceback,
            "context": {
                "surface": error.surface.value,
                "operation": error.operation,
                "player_id": error.player_id,
                "asset_id": error.asset_id,
                "live_event_id": error.live_event_id,
                "moderation_queue": error.moderation_queue,
            },
        },
        idempotency_key=request_id,
    )
    return CaptureResult(status="captured", group_key=key, event=event)


def get_client() -> InfraiClient:
    return InfraiClient()


app = FastAPI(title="Game backend error intake")


@app.post("/game-errors", response_model=CaptureResult)
def report_game_error(
    error: GameBackendError,
    client: Annotated[InfraiClient, Depends(get_client)],
) -> CaptureResult:
    try:
        return capture_game_error(error, client)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=dict(exc.detail)) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail="error backend response failed") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("game_error_service:app", host="127.0.0.1", port=8000)

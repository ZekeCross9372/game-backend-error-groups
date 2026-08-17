from game_error_service import GameBackendError, capture_game_error


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []

    def capture_error(self, payload: dict, *, idempotency_key: str) -> dict:
        self.calls.append((payload, idempotency_key))
        return {"event_id": "evt_test"}


def test_asset_failures_share_a_group_without_losing_entity_context() -> None:
    client = RecordingClient()
    first = GameBackendError(
        surface="player_asset",
        operation="publish",
        error_type="InvalidMesh",
        message="mesh has no vertices",
        traceback="InvalidMesh: mesh has no vertices",
        player_id="player-17",
        asset_id="asset-a",
    )
    second = first.model_copy(update={"player_id": "player-29", "asset_id": "asset-b"})

    result_a = capture_game_error(first, client)  # type: ignore[arg-type]
    result_b = capture_game_error(second, client)  # type: ignore[arg-type]

    assert result_a.group_key == result_b.group_key == (
        "player_asset:publish:InvalidMesh"
    )
    assert client.calls[0][0]["context"]["asset_id"] == "asset-a"
    assert client.calls[1][0]["context"]["asset_id"] == "asset-b"
    assert client.calls[0][1] != client.calls[1][1]

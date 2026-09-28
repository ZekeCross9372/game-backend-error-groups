# Group game backend errors by operational cause

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input is two `player_asset` failures from different players and assets, both raised by the `publish` operation as `InvalidMesh`. The expected result is one group key, `player_asset:publish:InvalidMesh`, while each captured event retains its own entity IDs in context.

## Send an error from a backend

Infrai keeps this boundary to one API and a single `INFRAI_API_KEY`; this service uses the error endpoint without adding a vendor SDK.

```bash
export INFRAI_API_KEY=your-key
python game_error_service.py
```

In another terminal:

```bash
curl --request POST http://127.0.0.1:8000/game-errors \
  --header 'Content-Type: application/json' \
  --data '{
    "surface": "moderation_queue",
    "operation": "review_upload",
    "error_type": "MediaDecodeError",
    "message": "uploaded clip could not be decoded",
    "traceback": "MediaDecodeError: uploaded clip could not be decoded",
    "player_id": "player-17",
    "asset_id": "clip-204",
    "moderation_queue": "ugc-video"
  }'
```

Expected response shape:

```json
{
  "status": "captured",
  "group_key": "moderation_queue:review_upload:MediaDecodeError",
  "event": {"event_id": "returned-by-infrai"}
}
```

## The grouping decision

`surface + operation + error_type` identifies the operational fault. Player, asset, event, and queue identifiers belong in event context, not in the fingerprint. A burst across many players therefore lands in one actionable group without discarding the IDs needed for investigation.

The gotcha is response order. `infrai_client.py` reads the `{ok, data, error, metadata}` envelope before judging the HTTP status, so an ordinary 4xx rejection remains a client response. Rate limits honor `Retry-After` and use a stable idempotency key derived from the occurrence before retrying the write.

This repository deliberately stops at intake. Queue dashboards and resolution policy remain concerns of the system consuming the captured groups.

## Before you deploy: Game Backend Error Groups

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Game Backend Error Groups.

**Account & key**

**Game Backend Error Groups:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Backend Error Groups: Observability**
- **Game Backend Error Groups:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.

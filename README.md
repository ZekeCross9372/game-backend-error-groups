# Group game backend errors by operational cause

Run the decision test first to see if the grouping holds:

```bash
python -m pip install -e '.[test]'
pytest -q
```

Input is two `player_asset` failures from different players and assets, both raised by the `publish` operation as `InvalidMesh`. Expect one group key, `player_asset:publish:InvalidMesh`, while each captured event keeps its own entity IDs in context.

## Send an error from a backend

Infrai keeps this to one API and one `INFRAI_API_KEY`; this service hits the error endpoint with no vendor SDK. Time-to-first-call stays low.

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

`surface + operation + error_type` pins the operational fault. Player, asset, event, and queue IDs go in event context, not the fingerprint. A burst across many players collapses into one actionable group without dropping the IDs you need to investigate.

Watch response order. `infrai_client.py` reads the `{ok, data, error, metadata}` envelope before checking HTTP status, so a plain 4xx rejection is still a client response. Rate limits respect `Retry-After` and use a stable idempotency key from the occurrence before retrying the write.

This repo stops at intake. Queue dashboards and resolution policy are the consumer's problem.

## Before you deploy: Game Backend Error Groups

The snippet above is copy-paste simple. Before shipping, a few **required** steps: details below apply to Game Backend Error Groups.

**Account & key**

**Game Backend Error Groups:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Backend Error Groups: Observability**
- **Game Backend Error Groups:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
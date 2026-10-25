# Dispatch / Core

Dispatch coordinates assignment through the Work Order, Workforce, and Notification
APIs. This directory contains Dispatch implementation, dependencies, database
startup configuration, API contracts, and tests. It adapts the GeoInspect reference
implementation; the other members' service implementations are not included.

## Implemented behavior

- Claim an idempotency key and assignment in one database transaction; reject a
  reused key with a changed payload. Replay completed success/rejection responses.
- Serialize orchestration across workers with PostgreSQL advisory locks. A bounded
  wait returns HTTP 202 for an identical request still being processed.
- Claim the work order, reserve an inspector slot, confirm the work order, and
  persist the confirmed assignment. Resume durable checkpoints with the same key
  after a transient failure or lost response.
- Release the work-order claim after a definite reservation rejection. Preserve
  unknown outcomes and unresolved compensation for same-key retry.
- Retry notification with exponential backoff and jitter and a stable delivery
  key. A failed/processing delivery keeps the assignment confirmed with notification
  PENDING. Only a SENT response records delivery; manual recovery is supported.
- Propagate correlation IDs and emit structured JSON orchestration logs.

## Run Dispatch

From the repository root, with Python 3.11–3.14 and Docker Desktop available:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/dispatch/requirements-dev.txt
Copy-Item services/dispatch/.env.example services/dispatch/.env
docker compose -f services/dispatch/docker-compose.yml up -d --wait
python -m services.dispatch
```

The example credentials are for the local demo database. The Compose file starts
only Dispatch's PostgreSQL database, exposed on port 55433. The service creates its
own tables at startup. Its `.env` file is read relative to this directory; process
environment variables take precedence. To change the database port, set
`DISPATCH_DB_PORT` for Compose and update `DISPATCH_DATABASE_URL` to match.

```powershell
Invoke-RestMethod http://127.0.0.1:8003/health
```

Swagger UI: `http://127.0.0.1:8003/docs`; generated schema:
`http://127.0.0.1:8003/openapi.json`. The checked-in-ready [schema](openapi.json)
is generated from this Dispatch application definition.

Health and assignment reads need only the Dispatch database. Creating an assignment
requires the other members' APIs at the configured addresses. Until they are
available, downstream failure returns a retryable HTTP 503. No full four-service
E2E claim is made by this standalone implementation.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISPATCH_PORT` | `8003` | Service listen port for `python -m services.dispatch` |
| `DISPATCH_DATABASE_URL` | PostgreSQL `dispatch_db` at `localhost:55433` | Dispatch-owned storage |
| `WORK_ORDER_URL` | `http://localhost:8001` | Work-order claim, confirm, and release |
| `WORKFORCE_URL` | `http://localhost:8002` | Inspector reservation |
| `NOTIFICATION_URL` | `http://localhost:8004` | Deduplicated delivery |
| `DOWNSTREAM_TIMEOUT_SECONDS` | `1.0` | Timeout for each downstream attempt |
| `NOTIFICATION_MAX_ATTEMPTS` | `3` | Total delivery attempts, bounded from 1 to 10 |
| `RETRY_BASE_SECONDS` | `0.15` | Exponential backoff base plus bounded jitter |
| `IDEMPOTENCY_WAIT_SECONDS` | `8.0` | Maximum wait for another worker's request |

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Check Dispatch database connectivity |
| POST | `/api/v1/assignments` | Orchestrate/replay; requires `Idempotency-Key` |
| GET | `/api/v1/assignments` | List saved assignments |
| GET | `/api/v1/assignments/{assignment_id}` | Read a saved assignment |
| POST | `/api/v1/assignments/{assignment_id}/retry-notification` | Retry delivery for a confirmed assignment |

The create payload contains UUID strings `work_order_id` and `inspector_id`.
Use the same `Idempotency-Key` and payload after HTTP 202 or retryable HTTP 503.
Completed responses are immutable: a later notification recovery changes the
assignment read endpoint, while the original create response still replays as
stored. Recovery is request driven; there is no background worker.

See [CONTRACTS.md](CONTRACTS.md) for the peer API requests and responses to agree
with the other service owners. Eligibility discovery remains Workforce-owned.

## Verification

Fast tests use a temporary SQLite database and a local lock double. Peer requests
go through HTTP contract doubles; no other member's implementation is imported.

```powershell
python -m pytest -c services/dispatch/pytest.ini
```

For real PostgreSQL idempotency, checkpoints, and cross-connection lock verification:

```powershell
$env:DISPATCH_TEST_DATABASE_URL = "postgresql+psycopg://dispatch_user:dispatch_pass@localhost:55433/dispatch_db"
python -m pytest -c services/dispatch/pytest.ini
Remove-Item Env:DISPATCH_TEST_DATABASE_URL
```

The database run creates and removes a generated test schema in Dispatch's database.
It needs schema-creation permission and never touches another service's database.
The two explicit PostgreSQL tests are skipped in the fast run. Both runs verify
Dispatch orchestration against contract doubles; final integration with the real
peer services remains to be performed after those implementations are delivered.

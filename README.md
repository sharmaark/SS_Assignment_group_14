# GeoInspect

GeoInspect coordinates location-based field inspections through REST APIs. A work
order identifies an inspection location, required skill, and scheduled slot.
Dispatch coordinates the work-order claim, inspector reservation, confirmation,
and notification while preserving request identity and progress across retries.

This branch provides the Dispatch service, its PostgreSQL persistence layer, API
contracts, and tests. Work Order, Workforce, and Notification communicate with
Dispatch through the documented [peer contracts](services/dispatch/CONTRACTS.md).
Their implementations are not included in this branch.

## Local execution

This guide uses Windows PowerShell and a locally installed PostgreSQL server.
Follow the blocks in order, from a fresh clone through persistent API requests
and automated verification. Long executable commands are written on single lines.

The live API example saves a `PENDING` assignment when its Work Order dependency
is unavailable. Successful assignment, concurrency, compensation, and recovery
are verified separately against controlled peer HTTP responses in tests.
A live `CONFIRMED` assignment requires the actual compatible peer services and
valid work-order and inspector records.

### 1. Check prerequisites

Install Git, Python 3.11–3.14, and PostgreSQL. Start the local PostgreSQL server
on port `5432` and have its administrator password available for one-time setup.
The commands have been verified with Python 3.14 and PostgreSQL 17 on Windows.

```powershell
git --version
python --version
```

### 2. Clone the Dispatch branch

The following creates the checkout in your Windows user directory:

```powershell
Set-Location -LiteralPath $env:USERPROFILE
git clone --branch feature/dispatch-integration https://github.com/sharmaark/SS_Assignment_group_14.git
Set-Location -LiteralPath (Join-Path $env:USERPROFILE 'SS_Assignment_group_14')
Get-Location
git branch --show-current
```

Expected branch: `feature/dispatch-integration`.

If you already have a checkout, skip cloning, enter its actual directory, and
switch to `feature/dispatch-integration`. Every relative file path below starts
at the repository root, which contains `README.md` and `services`.

### 3. Create the Python environment

```powershell
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r services/dispatch/requirements-dev.txt
Test-Path -LiteralPath '.venv/Scripts/python.exe'
```

The final command should return `True`. The commands use the environment's Python
executable directly, so PowerShell script activation is not required.

### 4. Locate the PostgreSQL command-line client

```powershell
$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $psql = Get-ChildItem -Path "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $psql) { throw 'psql.exe was not found. Install PostgreSQL or add its bin directory to PATH.' }
& $psql --version
```

This checks PATH and the standard Windows installation directory. For a custom
installation, assign the full path of its `psql.exe` to `$psql`.

### 5. Create the application role and database

Connect as the PostgreSQL administrator:

```powershell
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -W
```

Enter the administrator password. At the `postgres=#` prompt, paste this SQL.
These commands run inside `psql`, not directly in PowerShell.

```sql
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'group14_dispatch_user') THEN
        CREATE ROLE group14_dispatch_user LOGIN PASSWORD 'dispatch_pass';
    END IF;
END
$$;

ALTER ROLE group14_dispatch_user LOGIN PASSWORD 'dispatch_pass' VALID UNTIL 'infinity';

SELECT 'CREATE DATABASE group14_dispatch_db OWNER group14_dispatch_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'group14_dispatch_db')
\gexec

GRANT CONNECT, CREATE ON DATABASE group14_dispatch_db TO group14_dispatch_user;
\connect group14_dispatch_db
GRANT USAGE, CREATE ON SCHEMA public TO group14_dispatch_user;

SELECT current_database();
\q
```

The selected database should be `group14_dispatch_db`. `\q` returns to PowerShell.
The setup is repeatable and sets the dedicated role's local password explicitly,
including when the role already exists. These are local development credentials;
change the SQL and connection settings together if you choose another password.

### 6. Create the local configuration

From the repository root in PowerShell:

```powershell
if (Test-Path -LiteralPath 'services/dispatch/.env') {
    Copy-Item -LiteralPath 'services/dispatch/.env' -Destination ("services/dispatch/.env.backup-" + (Get-Date -Format 'yyyyMMddHHmmssfff'))
}
$dispatchEnv = @'
DISPATCH_PORT=8003
DISPATCH_DATABASE_URL=postgresql+psycopg://group14_dispatch_user:dispatch_pass@127.0.0.1:5432/group14_dispatch_db
WORK_ORDER_URL=http://127.0.0.1:18101
WORKFORCE_URL=http://127.0.0.1:8002
NOTIFICATION_URL=http://127.0.0.1:8004
DOWNSTREAM_TIMEOUT_SECONDS=1.0
NOTIFICATION_MAX_ATTEMPTS=3
RETRY_BASE_SECONDS=0.15
IDEMPOTENCY_WAIT_SECONDS=8.0
'@
$dispatchEnvPath = Join-Path (Get-Location).Path 'services/dispatch/.env'
[System.IO.File]::WriteAllText($dispatchEnvPath, $dispatchEnv + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
```

The file is written as UTF-8 without a byte-order mark, consistently in Windows
PowerShell 5.1 and PowerShell 7. The `.env` file and its backups are ignored by Git. Process environment variables
override values in this file. The local setup above supplies PostgreSQL port 5432,
overriding the reference defaults in the source and `.env.example`.

The standalone example uses an unavailable Work Order endpoint on port `18101`.
Keep that port unused for the dependency-outage example. You can check it with:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 18101 -InformationLevel Quiet -WarningAction SilentlyContinue
```

Expected: `False`. If it returns `True`, choose another unused port for
`WORK_ORDER_URL` before starting Dispatch. When connecting actual peer services,
use their agreed addresses and restart Dispatch. Do not point a peer URL at an
unrelated application simply because its port is listening.

### 7. Start Dispatch in Terminal A

Clear old shell overrides so the new `.env` values are used:

```powershell
Remove-Item Env:DISPATCH_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:WORK_ORDER_URL -ErrorAction SilentlyContinue
Remove-Item Env:WORKFORCE_URL -ErrorAction SilentlyContinue
Remove-Item Env:NOTIFICATION_URL -ErrorAction SilentlyContinue
Remove-Item Env:DISPATCH_PORT -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m services.dispatch
```

Wait for `Application startup complete` and the listener at `127.0.0.1:8003`.
Dispatch creates its own tables at startup. Keep this terminal running.
If an existing Dispatch process already passes its health check, use it instead
of starting a second server on the same port. Restart your own earlier process
if you need it to load changed settings.

### 8. Open Terminal B and check health

Open a second PowerShell window. For the clone location used in step 2:

```powershell
Set-Location -LiteralPath (Join-Path $env:USERPROFILE 'SS_Assignment_group_14')
Get-Location
Invoke-RestMethod 'http://127.0.0.1:8003/health'
```

For an existing checkout elsewhere, use its actual directory. Run all remaining
API, SQL-inspection, and test blocks in this same Terminal B so the request
variables remain available.

Expected:

```text
status service
------ -------
UP     dispatch
```

Open [Swagger UI](http://127.0.0.1:8003/docs). The running API schema is available
at [openapi.json](http://127.0.0.1:8003/openapi.json).

## Exercise the live API

### 9. Prepare a request

```powershell
$demoKey = 'local-' + [guid]::NewGuid().ToString()
$demoWorkOrderId = [guid]::NewGuid().ToString()
$demoInspectorId = [guid]::NewGuid().ToString()
$demoHeaders = @{ 'Idempotency-Key' = $demoKey; 'X-Correlation-ID' = 'local-dispatch' }
$demoBody = @{ work_order_id = $demoWorkOrderId; inspector_id = $demoInspectorId } | ConvertTo-Json
$demoBody
$demoKey
```

These are synthetic UUIDs, not records created in the peer services. Keep this
key and body for the retry. Running the preparation block again creates a new scenario.

### 10. Submit the request

```powershell
try {
    $demoResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8003/api/v1/assignments' -Headers $demoHeaders -ContentType 'application/json' -Body $demoBody
    Write-Output ('HTTP ' + $demoResponse.StatusCode)
    $demoResponse.Content
}
catch {
    if ($null -eq $_.Exception.Response) { throw }
    Write-Output ('HTTP ' + [int]$_.Exception.Response.StatusCode)
    $_.ErrorDetails.Message
}
```

With Work Order unavailable, expect HTTP `503` and `WORK_ORDER_UNAVAILABLE`.
Dispatch commits the assignment and idempotency record before the downstream call.
The assignment remains `PENDING` at stage `CREATED`, ready for same-key recovery.

The catch block displays HTTP errors in Windows PowerShell and PowerShell 7.
A connection failure to Dispatch itself is rethrown rather than presented as an
application response.

### 11. Read the persisted assignment

```powershell
$demoList = Invoke-RestMethod 'http://127.0.0.1:8003/api/v1/assignments'
$demoMatches = @($demoList.items | Where-Object { $_.work_order_id -eq $demoWorkOrderId -and $_.inspector_id -eq $demoInspectorId })
if ($demoMatches.Count -ne 1) { throw 'Expected exactly one saved assignment for this request.' }
$demoAssignment = $demoMatches[0]
$demoAssignment | ConvertTo-Json -Depth 10
```

Read the individual record:

```powershell
Invoke-RestMethod ('http://127.0.0.1:8003/api/v1/assignments/' + $demoAssignment.id) | ConvertTo-Json -Depth 10
```

The returned `id` identifies the saved assignment. `reservation_id` is null because
the request has not reached reservation.

### 12. Inspect the same records in PostgreSQL

Locate `psql` in Terminal B; Terminal A's variables are not shared:

```powershell
$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $psql = Get-ChildItem -Path "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $psql) { throw 'psql.exe was not found. Set $psql to its full installation path.' }
$env:PGPASSWORD = 'dispatch_pass'
```

Read the assignment using its own database role:

```powershell
& $psql -h 127.0.0.1 -p 5432 -U group14_dispatch_user -d group14_dispatch_db -c "SELECT id, work_order_id, inspector_id, status, stage, reservation_id, notification_status FROM public.assignments WHERE id = '$($demoAssignment.id)';"
```

Read the associated request record:

```powershell
& $psql -h 127.0.0.1 -p 5432 -U group14_dispatch_user -d group14_dispatch_db -c "SELECT key, assignment_id, status_code, response_body FROM public.idempotency_records WHERE key = '$demoKey';"
```

Both records persist in the `public` schema. While processing is unfinished,
`status_code` and `response_body` remain null: the temporary 503 is not frozen
as the permanent terminal response.

### 13. Repeat the original request

Send the same key and body again:

```powershell
try {
    $demoResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8003/api/v1/assignments' -Headers $demoHeaders -ContentType 'application/json' -Body $demoBody
    Write-Output ('HTTP ' + $demoResponse.StatusCode)
    $demoResponse.Content
}
catch {
    if ($null -eq $_.Exception.Response) { throw }
    Write-Output ('HTTP ' + [int]$_.Exception.Response.StatusCode)
    $_.ErrorDetails.Message
}
```

Expect HTTP 503 while the dependency is unavailable. Check that the identity was reused:

```powershell
$demoList = Invoke-RestMethod 'http://127.0.0.1:8003/api/v1/assignments'
$demoMatches = @($demoList.items | Where-Object { $_.work_order_id -eq $demoWorkOrderId })
Write-Output ('Assignments for this request: ' + $demoMatches.Count)
$demoMatches | Select-Object id, status, stage
```

Expected count: `1`, with the same assignment ID. An unfinished request resumes
under its existing identity. A completed request replays its stored final response.

### 14. Reject a changed payload under the same key

```powershell
$demoChangedBody = @{ work_order_id = $demoWorkOrderId; inspector_id = [guid]::NewGuid().ToString() } | ConvertTo-Json
try {
    $demoResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8003/api/v1/assignments' -Headers $demoHeaders -ContentType 'application/json' -Body $demoChangedBody
    Write-Output ('HTTP ' + $demoResponse.StatusCode)
    $demoResponse.Content
}
catch {
    if ($null -eq $_.Exception.Response) { throw }
    Write-Output ('HTTP ' + [int]$_.Exception.Response.StatusCode)
    $_.ErrorDetails.Message
}
```

Expected: HTTP `409` and `IDEMPOTENCY_KEY_REUSED`. The changed payload is rejected
before another downstream workflow starts.

## Automated verification

### 15. Enable PostgreSQL-backed tests

In Terminal B:

```powershell
$env:DISPATCH_TEST_DATABASE_URL = 'postgresql+psycopg://group14_dispatch_user:dispatch_pass@127.0.0.1:5432/group14_dispatch_db'
```

The tests run real Dispatch routes and PostgreSQL persistence with HTTP contract
doubles for the peer services. Each test creates a generated `dispatch_test_...`
schema and removes it afterward. The live record above stays in `public.assignments`.

### Successful assignment, exact replay, and payload conflict

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_assignment_replay_preserves_response_and_forwards_contract_and_correlation -vv
```

Expected: `1 passed`. Checks confirmation, notification, exact completed replay,
forwarded fields, correlation ID, and one downstream flow.

### Concurrent duplicates

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_simultaneous_duplicates_execute_one_flow -vv
```

Expected: `1 passed`. Eight copies share one assignment and result.

### Bounded duplicate waiting

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_duplicate_wait_is_bounded -vv
```

Expected: `1 passed`. A waiting duplicate receives HTTP 202 when its limit expires.

### Lost committed responses

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_lost_committed_response_resumes_same_assignment -vv
```

Expected: `3 passed`, covering claim, reservation, and confirmation response loss.

### Retryable downstream server errors

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_server_error_is_retryable_without_releasing_unknown_outcome -vv
```

Expected: `2 passed`. Unknown outcomes remain available for recovery.

### Definite rejection and claim release

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_definite_rejection_releases_claim_and_replays_without_side_effects -vv
```

Expected: `1 passed`. The matching claim is released and rejection is replayable.

### Unresolved compensation

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_unresolved_compensation_is_not_stored_as_terminal_rejection -vv
```

Expected: `1 passed`. An unresolved release is not stored as a completed rejection.

### Notification failure and manual recovery

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_notification_failure_preserves_confirmation_and_manual_retry_keeps_stored_response -vv
```

Expected: `2 passed`. Delivery recovery preserves confirmation and the original response.

### Lost notification response

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_lost_notification_response_reuses_delivery_key -vv
```

Expected: `1 passed`. Delivery retry reuses the stable key.

### Failure after confirmation but before response storage

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_api.py::test_confirmed_checkpoint_survives_failure_before_response_storage -vv
```

Expected: `1 passed`. Saved confirmation avoids repeating completed operations.

### PostgreSQL locking and durable checkpoints

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini services/dispatch/tests/test_postgres.py -vv
```

Expected: `2 passed`, using separate database connections.

### Complete suite

```powershell
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini -vv
```

Expected with the current implementation: `37 passed`. Dependency deprecation
warnings may appear. The full suite also checks input/configuration validation,
fingerprints, backoff, malformed downstream responses, transport failures,
assignment reads, and documented API outcomes.

For a fast run without PostgreSQL integration:

```powershell
Remove-Item Env:DISPATCH_TEST_DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest -c services/dispatch/pytest.ini -vv
```

Expected: `35 passed, 2 skipped`. This uses temporary SQLite storage and a local
lock double. Set the test database variable again for real PostgreSQL verification.

### 16. Confirm the live record survived test cleanup

In the same Terminal B:

```powershell
Invoke-RestMethod ('http://127.0.0.1:8003/api/v1/assignments/' + $demoAssignment.id) | ConvertTo-Json -Depth 10
```

The record should still exist. Test cleanup removes only generated schemas,
not the application's public records.

## API and implementation

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check Dispatch database connectivity |
| POST | `/api/v1/assignments` | Create, resume, or replay a request |
| GET | `/api/v1/assignments` | List persisted assignments |
| GET | `/api/v1/assignments/{assignment_id}` | Read one assignment |
| POST | `/api/v1/assignments/{assignment_id}/retry-notification` | Retry notification for a confirmed assignment |

Assignment creation requires UUID `work_order_id` and `inspector_id` values and
an `Idempotency-Key` header of 1–100 characters. `X-Correlation-ID` is propagated
or generated when absent.

| Status | Meaning |
| --- | --- |
| 201 | Confirmed assignment or replay of its stored response |
| 202 | An identical request remains in progress beyond the waiting limit |
| 404 | Assignment or required peer resource not found |
| 409 | Business conflict, changed payload under one key, or retry on an unconfirmed assignment |
| 422 | Input validation failed |
| 503 | Downstream outcome unresolved; retry the original payload and key |

| File | Responsibility |
| --- | --- |
| [api.py](services/dispatch/src/api.py) | Validation, correlation, endpoints, orchestration, and notification retry |
| [business.py](services/dispatch/src/business.py) | Canonical fingerprints, key checks, and retry delays |
| [data.py](services/dispatch/src/data.py) | Models, transactions, checkpoints, and execution locks |
| [clients.py](services/dispatch/src/clients.py) | HTTP calls, timeouts, and downstream error translation |
| [config.py](services/dispatch/src/config.py) | Environment settings and validated runtime limits |
| [tests](services/dispatch/tests/) | Business, API, failure, and database verification |

Each service owns its database. Dispatch uses local transactions for request
claims and checkpoints, and PostgreSQL advisory locks to coordinate workers.
Lock connections are separate from checkpoint-write connections. Cross-service
progress is coordinated through APIs rather than a global database transaction.

Definite reservation rejection triggers matching claim release. Unknown outcomes
stay recoverable under the same identity. Notification follows confirmation,
using a stable delivery key, bounded retries, backoff, and jitter. Only an explicit
`SENT` result records delivery. Recovery is request driven; there is no background worker.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Python executable is not recognised | Run `Get-Location`, enter the repository root, and repeat step 3. |
| Health cannot connect | Check Terminal A for startup errors and keep the service running. |
| Database authentication fails | Repeat step 5 and ensure SQL and `.env` credentials match. |
| Connection uses port 55433 | Complete step 6 and clear old shell overrides in step 7; this guide uses 5432. |
| Port 8003 is occupied | Check the existing health endpoint. Use the running Dispatch process or stop only your own earlier process before restarting. |
| Live creation returns 503 | Expected for the configured dependency outage; inspect the saved PENDING record. |
| A peer responds with another application's output | Correct the peer URL and restart Dispatch. A listening port does not identify the service. |
| Public tables are empty after tests | Tests use temporary schemas. Use steps 9–12 for persistent application records. |
| PostgreSQL cases are skipped | Set `DISPATCH_TEST_DATABASE_URL` in the terminal running pytest. |
| Request variables are missing | Keep steps 9–16 in one Terminal B and repeat the request preparation/read blocks. |

## Stop the application

Press **Ctrl+C** in Terminal A. Clear temporary settings in Terminal B:

```powershell
Remove-Item Env:DISPATCH_TEST_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
```

Stopping Dispatch leaves its PostgreSQL records intact.

## Further documentation

- [Peer API contracts](services/dispatch/CONTRACTS.md)
- [Dispatch OpenAPI specification](services/dispatch/openapi.json)
- [Architecture](docs/architecture.md)
- [Design diagrams](docs/diagrams/)
- [Service ownership](TEAM.md)

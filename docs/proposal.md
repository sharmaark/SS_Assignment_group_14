# GeoInspect: one-week assignment scope

## Goal

Build an API-only GIS field inspection dispatch application that meets Assignment 1 requirements in seven days. Use synthetic utility asset locations, inspector service areas, and fixed inspection slots. The application assigns a selected inspector to an inspection; it does not automatically find or rank inspectors.

This document supersedes the earlier three-week proposal. It specifies planned behaviour, not completed implementation or evidence.

Group 14 starts from documentation only. In addition to the minimum selected-inspector
flow below, Workforce will add availability and eligible-inspector discovery;
[TEAM.md](../TEAM.md) defines the current member ownership and delivery workflow.

## Minimum application

| Service | Business responsibility | Owned database records |
|---|---|---|
| Work Order | Manage inspection state and evidence | Work orders: location, required skill, slot, state, assignment ID; photo metadata and GridFS files |
| Workforce | Check inspector eligibility and prevent double-booking | Inspectors, rectangular service areas, skills, slot reservations |
| Dispatch | Coordinate assignment and prevent duplicate assignment requests | Assignments, transaction stage, idempotency key, fingerprint, stored response |
| Notification | Simulate sending inspection confirmations and deduplicate delivery | Notification records and delivery results |

Use Python/FastAPI, PostgreSQL, MongoDB, pytest, and Python HTTP scripts. Workforce and Dispatch use separate PostgreSQL databases because their uniqueness constraints protect concurrency and idempotency. Work Order uses its own MongoDB database and GridFS bucket for photos. Notification uses another MongoDB database. Each database has separate credentials, and services communicate through HTTP only.

Store photo metadata in normal MongoDB documents and binary files in GridFS; never embed base64 images in a work-order document. Accept JPEG and PNG files up to a configurable 10 MB each. The minimum photo API uploads, lists, and downloads evidence for a work order. Photos remain a small supporting feature so they do not displace the assessed distributed-system work. Object storage with MongoDB metadata is the preferred production design, but GridFS keeps this one-week submission self-contained.

GIS scope: longitude/latitude points in EPSG:4326 and seeded rectangular service areas that do not cross the antimeridian. Boundary-inclusive bounds checks are enough for this dataset; document the geographic limitation. No spatial database extension is needed.

## Main flow

Client calls `POST /api/v1/assignments` with a work-order ID, selected inspector ID, and `Idempotency-Key`.

1. Dispatch atomically claims the idempotency key and creates a PENDING assignment.
2. Work Order atomically claims the OPEN work order for that assignment and returns its location, skill, and fixed slot.
3. Workforce validates coverage and skill, then reserves the inspector slot using a database uniqueness constraint.
4. Work Order marks the claimed inspection ASSIGNED; Dispatch records CONFIRMED.
5. Dispatch calls Notification with a stable delivery key. Successful delivery records SENT. Timeout or failure records notification status PENDING and still returns the confirmed assignment.

All participant mutations use the assignment ID as a stable operation identity. Reject a second assignment for an already claimed work order. If reservation is definitively rejected, release the matching work-order claim and mark the assignment REJECTED.

Keep minimal persisted stages so a repeated request can resume an interrupted operation. A timeout after a write has an unknown outcome: query or replay that same operation ID before deciding the next step. Do not release a potentially confirmed reservation merely because an HTTP response was lost. Full automatic crash recovery and background workers are outside the one-week scope; unresolved operations remain PENDING and can be resumed with the same request. State this limitation in the report.

Use a manual `POST /api/v1/assignments/{id}/retry-notification` API to retry pending delivery after the mock service recovers. No broker or scheduled worker is needed.

States:

- Work Order: OPEN → CLAIMED → ASSIGNED; a matching failed reservation allows CLAIMED → OPEN.
- Assignment: PENDING → CONFIRMED or REJECTED.
- Reservation: RESERVED, owned by exactly one assignment.
- Assignment notification status: PENDING → SENT.

## Required business rules and tests

| Rule | Enforcement | Unit test |
|---|---|---|
| BR1: Inspector area covers the inspection location | Workforce bounds check, including boundaries | Inside/outside/boundary coordinates |
| BR2: Inspector has the required skill | Workforce eligibility logic | Skill match and mismatch |
| BR3: Inspector cannot be booked twice in the same slot | Workforce unique constraint on inspector and slot | Reservation conflict mapped to a meaningful error |
| BR4: Only the owning assignment can confirm a work order | Work Order state transition and conditional update | Wrong owner and invalid transition rejected |
| BR5: Same idempotency key with a different payload is rejected | Dispatch stored canonical fingerprint | Payload mismatch produces HTTP 409 |
| BR6: Photos can be attached only to an assigned work order and must meet type/size limits | Work Order upload validation | State, content-type, and size cases |

Database integration and challenge scripts supplement unit tests; a mocked unit test alone does not prove concurrency safety.

## Exactly three engineering challenges

### 1. Concurrency — mandatory

Seed one inspector slot with capacity N = 1 and 20 eligible work orders for that slot. Send 20 parallel assignments with distinct keys. Assert exactly one succeeds and 19 receive a meaningful conflict. Verify one reservation, one confirmed assignment, and released claims for rejected requests. Explain why check-then-update allows races and how the database constraint prevents them.

### 2. Idempotency — mandatory

Store key, request fingerprint, and terminal response in Dispatch. A unique constraint chooses one owner; simultaneous duplicates wait for the same result and do not execute separate flows. If processing outlasts the bounded wait, return HTTP 202 with the existing assignment ID; retries eventually replay the stored terminal response. The normal simultaneous-duplicate demo must obtain the same terminal response for both requests.

Show first request, sequential repeats, two simultaneous identical requests, and a changed payload returning HTTP 409. Verify one assignment, one reservation, and one notification. Notification also deduplicates on its stable delivery key, including concurrent attempts.

### 3A. Resilience — chosen optional challenge

Only Notification needs the resilience demonstration:

- Configurable HTTP timeout.
- Three total attempts with exponential backoff and jitter; document exact values.
- Mock modes for normal delivery, slow response, and deliberate failure.
- Stop Notification and show a confirmed assignment with notification PENDING after bounded retries.
- Restart it and retry delivery through the API.
- Simulate delivery committed before a delayed response; retry the same delivery key and verify one notification record/effect.

Log each attempt and delay. No circuit breaker, broker, hold-expiry job, or full saga is required.

## Minimum API and operability checklist

- Versioned business paths `/api/v1/...`, input validation, correct status codes, and one common JSON error format.
- `GET /health` for all four services; export each service's generated OpenAPI JSON to `docs/openapi/`.
- Ports, PostgreSQL and MongoDB connections, peer URLs, photo size limit, mock modes, timeout, and retry settings come from environment variables.
- Structured JSON logs; propagate `X-Correlation-ID` through service calls.
- README with prerequisites, database setup, commands to run each service, ports, environment variables, seed data, tests, and challenge scripts.
- A simple Python API client; no UI, authentication, photo analysis, thumbnails, real SMS, payments, routing, nearest-inspector search, arbitrary scheduling, or dashboards.
- Defer application containerisation and Minikube to Assignment 2. Keep configuration and process startup compatible with that later work.

## Seven-day plan

| Day | Work | Completion checkpoint |
|---|---|---|
| 1 | Freeze scope, create four service skeletons and isolated databases; health, config, logging, schema/API drafts | Four services start independently; outline report and diagrams |
| 2 | Work Order transitions and minimal GridFS photo API; Workforce GIS/skill checks and atomic slot reservation; rule tests | Eligibility, evidence upload, and reservation work; concurrent reservation correctness verified |
| 3 | Dispatch main flow and persisted idempotency; Notification deduplication | Happy-path end-to-end script and simultaneous replay pass |
| 4 | Notification timeouts, backoff/jitter, mock failures, manual retry | Challenge 3A passes, including response-loss duplicate test |
| 5 | Run all tests and three challenge scripts; capture outputs, logs, DB state | Evidence folders contain timestamped success and failure evidence |
| 6 | Finalise report, diagrams, README, OpenAPI exports; run from a fresh clone | Another team member can run it using README only |
| 7 | Fix remaining issues; record 8–10 minute live demo; final submission check | Repository accessible, report PDF and video/Drive links ready |

Keep a little report work alongside implementation; days 6–7 should focus on verification and delivery rather than new features.

## Required submission artefacts

- GitHub repository accessible to faculty.
- Design report PDF, at most 15 pages excluding appendices; target 8–10 main pages.
- Report includes problem/scope and rules; service decomposition; component diagram; happy/failure sequence diagrams; ER diagram per service; ownership table; endpoint table and examples; error model and OpenAPI links; challenges and evidence; testing results; at least three design trade-offs; limitations/future work; video/Drive link.
- `evidence/challenge-1-concurrency/`, `evidence/challenge-2-idempotency/`, `evidence/challenge-3a-resilience/`, and `evidence/tests/`, with READMEs mapping files to claims. Include raw text logs and final DB state; screenshots used as evidence must show command, output, and timestamp.
- An 8–10 minute video showing actual API calls and challenge scripts, including failure handling. Every member speaks.
- Actual contribution table, one half-page reflection per student, accurate AI-use declaration, and commit history reflecting each member's work.

Three report decisions: fixed slots versus arbitrary intervals; central REST coordination versus event choreography; geographic coverage checks versus routing/optimisation. Explain the selected option and its limitations.

## Scope freeze

Add no features unless required to make the mandated flow, rules, tests, evidence, or deliverables correct. The one-week target depends on protecting this scope and reserving the last two days for report, fresh-clone verification, and video.

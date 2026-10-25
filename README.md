# GeoInspect — Group 14

Scalable Services (SEZG583), Assignment 1: a planned API-only GIS field-inspection
dispatch application.
as a design reference.

## Repository status

Members added application code, tests, dependencies, database setup, startup
tooling, and verification evidence through their own commits and pull requests.

## Members and branches

| Member | Branch | Ownership |
| --- | --- | --- |
| Nia | [`feature/workforce-discovery`](https://github.com/sharmaark/SS_Assignment_group_14/tree/feature/workforce-discovery) | Workforce service, eligibility/reservations, availability, and eligible-inspector discovery |
| Rishi | [`feature/dispatch-integration`](https://github.com/sharmaark/SS_Assignment_group_14/tree/feature/dispatch-integration) | Dispatch orchestration, idempotency, shared run/integration tooling, and final E2E verification |
| Venkat | [`feature/workorder-enhancement`](https://github.com/sharmaark/SS_Assignment_group_14/tree/feature/workorder-enhancement) | Work Order service, GIS/state validation, lifecycle, and photo handling |
| Ujjawal | [`feature/notification-resilience`](https://github.com/sharmaark/SS_Assignment_group_14/tree/feature/notification-resilience) | Notification service, delivery deduplication, failure/recovery, and resilience |

See [TEAM.md](TEAM.md) for responsibilities and the contribution workflow.

## Planned application

A work order records a map location, required skill, and inspection slot.
Dispatch coordinates Work Order, Workforce, and Notification so an eligible
inspector is reserved once and the result can be replayed safely. Notification
failures must preserve confirmed assignments and support recovery.

| Planned service | Port | Owned data store |
| --- | --- | --- |
| Work Order | 8001 | MongoDB work orders and GridFS inspection photos |
| Workforce | 8002 | PostgreSQL inspectors and slot reservations |
| Dispatch | 8003 | PostgreSQL assignments and idempotency records |
| Notification | 8004 | MongoDB delivery records |

Services communicate through APIs; each service owns its own database.
These are design decisions, not a claim of completed implementation.


## Design documents

- [Documentation guide](docs/README.md)
- [Planned scope and verification requirements](docs/proposal.md)
- [Proposed architecture](docs/architecture.md)
- [Design diagrams](docs/diagrams/)

The proposal and diagrams are planning material adapted from the reference
project. Group 14 implementation, tests, evidence, and final reports are
added through the members' own contributions.

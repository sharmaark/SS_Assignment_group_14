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
| Nia | [`feature/workforce-discovery`](https://github.com/sharmaark/SS_Assignment_group_14/tree/feature/workforce-discovery) | Workforce service, eligibility/reservations, availability, and eligible-inspector discovery. **Assignment 2:** Workforce containerization and optional advanced Minikube/Kubernetes deployment integration, including Kubernetes workflow verification, 3-replica Workforce scaling, self-healing verification, and deployment evidence. |
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

## Assignment 2 — Nia advanced deployment contribution

Nia extended her Workforce ownership into the optional Assignment 2 advanced
deployment work. This work was implemented and verified on Minikube/Kubernetes
without changing the business ownership of the other team services.

### Kubernetes deployment integration

The advanced deployment configuration includes:

- a dedicated `geoinspect` Kubernetes namespace
- PostgreSQL deployment/service for Workforce and Dispatch persistence
- MongoDB deployment/service required by Work Order
- Workforce Kubernetes Deployment and Service
- Work Order Kubernetes Deployment and Service for integration of the existing team service
- Dispatch Kubernetes Deployment and Service for integration of the existing team service
- Kubernetes DNS-based service communication instead of `localhost` addresses
- readiness/liveness health checks for deployed services
- reproducible Kubernetes manifests under `k8s/`

Nia's Assignment 2 work containerizes/integrates services for deployment; it
does not change ownership of the Work Order or Dispatch business implementations.

### Kubernetes workflow verification

A real core assignment workflow was executed through the Kubernetes deployment:

1. A Work Order was created through the Kubernetes Work Order service.
2. An `ELECTRICAL` inspector was created through the Kubernetes Workforce service.
3. Workforce Smart Inspector Discovery verified skill, GIS/service-area, and slot eligibility.
4. Inspector availability was verified as `true` before assignment.
5. An assignment was submitted through the Kubernetes Dispatch service using an idempotency key.
6. Dispatch claimed the Work Order, reserved the inspector through Workforce, and confirmed the Work Order.
7. The persisted assignment reached `status = CONFIRMED` and `stage = CONFIRMED` with a reservation ID.
8. Workforce availability changed from `true` to `false` after reservation.

The current team integration snapshot does not contain the Notification service.
The existing Dispatch implementation preserves the confirmed assignment while
notification delivery remains `PENDING`; no fake Notification implementation was
added for the Kubernetes demonstration.

### Kubernetes scaling and self-healing

Workforce was scaled from **1 replica to 3 replicas**. All three replicas reached
Ready/Running state.

One running Workforce pod was then deleted during the self-healing demonstration.
Kubernetes automatically created a replacement pod and restored the desired
Workforce replica count to **3/3**. The Workforce health endpoint remained
operational after recovery.

Evidence for Nia's Assignment 2 advanced deployment work is stored under:

`evidence/assignment2/nia/`

## Design documents

- [Documentation guide](docs/README.md)
- [Planned scope and verification requirements](docs/proposal.md)
- [Proposed architecture](docs/architecture.md)
- [Design diagrams](docs/diagrams/)

The proposal and diagrams are planning material adapted from the reference
project. Group 14 implementation, tests, evidence, and final reports are
added through the members' own contributions.

# Group 14 — GeoInspect ownership and delivery

This repository starts with planning documents and Git configuration, using
[GeoInspect](https://github.com/sharmaark/SS_Assignment) as a design reference.
All four member branches start at the same documentation-only commit.
Service implementations will be contributed by their owners through pull requests.

## Four member branches

| Member | Branch | Assigned work |
| --- | --- | --- |
| Nia | `feature/workforce-discovery` | Implement Workforce: inspector records, GIS/skill eligibility, atomic slot reservations, availability API, and eligible-inspector discovery. Own service database setup, dependencies, tests, OpenAPI, and demo/evidence. **Assignment 2:** Own Workforce containerization and the optional advanced Minikube/Kubernetes deployment integration, including Kubernetes workflow verification, Workforce scaling/self-healing, and advanced deployment evidence. |
| Rishi | `feature/dispatch-integration` | Implement Dispatch/Core orchestration and idempotency; integrate the other services' APIs. Coordinate shared database startup/run tooling and own final E2E/integration verification. |
| Venkat | `feature/workorder-enhancement` | Implement Work Order: GIS/work-order validation, lifecycle transitions, claim/confirm/release APIs, and photo handling. Own service database setup, dependencies, tests, OpenAPI, and demo/evidence. |
| Ujjawal | `feature/notification-resilience` | Implement Notification: deduplicated delivery, mock provider behavior, failure/recovery handling, resilience tests, and a circuit breaker if feasible. Own service database setup, dependencies, OpenAPI, and demo/evidence. |

There are four feature branches in addition to `main`. The table above defines
each member's scope. No implementation is preloaded on any branch.

## Starting status

The initial commit contains planning documents and Git configuration only.
Application code, tests, database scripts, startup tooling, dependencies,
generated API exports, execution evidence, and the final report remain to be
contributed. Design documents describe intended behavior rather than test results.

## Working on a branch

```powershell
git clone https://github.com/sharmaark/SS_Assignment_group_14.git
cd SS_Assignment_group_14
git switch --track origin/feature/workforce-discovery
```

Replace the example branch with your assigned branch. Configure your own Git
name/email and authenticate with your own GitHub account. Add setup/run
instructions with your implementation. Keep changes in your service and its
tests, API contracts, and evidence; coordinate shared files with Rishi.

## Integration workflow

1. Agree API requests, responses, and failure behavior with the service owners
   before implementing contracts consumed by Dispatch.
2. Each member implements and tests their own service, exports OpenAPI where
   relevant, and records actual synthetic demo/evidence.
3. Push the assigned feature branch and open a pull request targeting `main`.
   The description should explain the actual implementation and validation.
4. Merge reviewed service implementations when their checks pass. Rishi brings
   the agreed changes into `feature/dispatch-integration` and runs the combined
   E2E, concurrency, idempotency, and resilience checks.
5. Merge final Dispatch integration after combined verification is complete.
   Use merge commits so each member's individual commits remain visible. Avoid
   squashing the team implementation into a single combined author commit.

Each service owns its own database. Cross-service integration uses APIs.
GitHub access can be granted separately using the members' actual usernames.

## Nia — Assignment 2 advanced deployment contribution

Nia extended her Assignment 1 Workforce ownership into the optional advanced
deployment work for Assignment 2. The work below describes deployment and
integration responsibility only; existing Work Order and Dispatch business logic
remains owned by their assigned members.

### Workforce containerization

Nia's Assignment 2 Workforce deployment work includes:

- Workforce Dockerfile and container-safe Uvicorn startup
- environment-based Workforce database configuration
- container networking through PostgreSQL service DNS rather than `localhost`
- Docker image build and health verification
- Workforce deployment preparation for Minikube/Kubernetes

### Minikube/Kubernetes deployment integration

Nia implemented and verified Kubernetes configuration for the advanced deployment,
including:

- `geoinspect` namespace
- PostgreSQL Deployment and Service
- PostgreSQL initialization for `workforce_db` / `workforce_user` and `dispatch_db` / `dispatch_user`
- MongoDB Deployment and Service
- MongoDB initialization for `work_order_db` / `work_order_user`
- Workforce Deployment and Service
- Work Order Deployment and Service for deployment of Venkat's existing Work Order implementation
- Dispatch Deployment and Service for deployment of Rishi's existing Dispatch implementation
- Kubernetes DNS-based downstream URLs (`postgres`, `mongodb`, `work-order`, `workforce`, `dispatch`)
- readiness/liveness probes
- reproducible manifests stored under `k8s/`

### Kubernetes workflow verification

Nia verified an actual core GeoInspect workflow through the Kubernetes deployment:

1. Created a Work Order through the Kubernetes Work Order service.
2. Created an `ELECTRICAL` inspector through the Kubernetes Workforce service.
3. Verified Smart Inspector Discovery using skill, GIS/service-area, and slot availability.
4. Verified inspector availability as `true` before assignment.
5. Submitted an assignment through Kubernetes Dispatch with an `Idempotency-Key`.
6. Dispatch claimed the Work Order.
7. Dispatch reserved the inspector through Workforce.
8. Dispatch confirmed the Work Order.
9. The persisted assignment reached `status = CONFIRMED` and `stage = CONFIRMED` with a reservation ID.
10. Workforce availability changed from `true` to `false` after the reservation.

The current team integration snapshot does not contain the Notification service.
The existing Dispatch implementation treats notification delivery as a recoverable
secondary operation, so the confirmed assignment remains valid while
`notification_status = PENDING`. No fake Notification service was introduced for
the advanced deployment demonstration.

### Kubernetes scaling and self-healing

Nia implemented and demonstrated Workforce horizontal scaling:

`1 replica → 3 replicas`

All three Workforce replicas reached Ready/Running state. One running Workforce
pod was then manually deleted. Kubernetes automatically created a replacement pod
and restored the configured desired state to `3/3` ready replicas. Workforce
remained operational after recovery.

### Assignment 2 evidence

Nia's advanced deployment evidence is stored under:

`evidence/assignment2/nia/`

The evidence records:

- Kubernetes node information
- deployments, pods, and Services
- the confirmed Kubernetes assignment workflow
- post-assignment Work Order state
- Workforce availability after reservation
- three-replica Workforce state
- scaling and self-healing verification

## Contribution records

Commit implementation and tests in understandable steps, with messages that
describe the actual work. Add generated OpenAPI and execution evidence only
after running the corresponding implementation. Keep reference-code reuse and
AI-assistance declarations accurate in the final report and contribution table.

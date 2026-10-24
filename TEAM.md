# Group 14 — GeoInspect ownership and delivery

This repository starts with planning documents and Git configuration, using
[GeoInspect](https://github.com/sharmaark/SS_Assignment) as a design reference.
All four member branches start at the same documentation-only commit.
Service implementations will be contributed by their owners through pull requests.

## Four member branches

| Member | Branch | Assigned work |
| --- | --- | --- |
| Nia | `feature/workforce-discovery` | Implement Workforce: inspector records, GIS/skill eligibility, atomic slot reservations, availability API, and eligible-inspector discovery. Own service database setup, dependencies, tests, OpenAPI, and demo/evidence. |
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

## Contribution records

Commit implementation and tests in understandable steps, with messages that
describe the actual work. Add generated OpenAPI and execution evidence only
after running the corresponding implementation. Keep reference-code reuse and
AI-assistance declarations accurate in the final report and contribution table.

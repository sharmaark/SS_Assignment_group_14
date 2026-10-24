# GeoInspect design documents

These files describe the proposed system. They do not certify that Group 14 has
implemented or tested the services.

| Document | Purpose |
| --- | --- |
| [proposal.md](proposal.md) | Planned scope, business rules, verification scenarios, and submission requirements |
| [architecture.md](architecture.md) | Proposed API interactions, state transitions, and data ownership |
| [diagrams/](diagrams/) | Editable draw.io design diagrams and their PDF exports |

The original design assumes a client selects an inspector. Group 14's Workforce
scope also includes availability and eligible-inspector discovery, as assigned
in [TEAM.md](../TEAM.md). A circuit breaker is optional if feasible. Update the
design and API contracts as these decisions are implemented.

Service owners will add generated OpenAPI under `docs/openapi/` after their
services exist. Members will add test outputs and demo records under `evidence/`
after verification, and prepare the submission report from those actual results.
The initial baseline has no implementation, generated API exports, execution
evidence, or final submission report.

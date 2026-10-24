# GeoInspect architecture

This is the proposed design adapted from the GeoInspect reference project.
Group 14's implementations and verification evidence will be delivered on the
member branches described in [TEAM.md](../TEAM.md).

## Component view

```mermaid
flowchart LR
    Client[API client / challenge scripts] -->|REST + Idempotency-Key| Dispatch
    Dispatch -->|claim / confirm work order| WorkOrder[Work Order service]
    Dispatch -->|reserve inspector slot| Workforce[Workforce service]
    Dispatch -->|deduplicated delivery| Notification[Notification mock service]
    WorkOrder -->|owned data| WOMongo[(MongoDB work_order_db)]
    Workforce -->|owned data| WFPostgres[(PostgreSQL workforce_db)]
    Dispatch -->|owned data| DPostgres[(PostgreSQL dispatch_db)]
    Notification -->|owned data| NMongo[(MongoDB notification_db)]
    WOMongo --> GridFS[(GridFS photo bucket)]
```

All arrows between services are HTTP. No service reads another service's database. `X-Correlation-ID` is copied along the full request path.

## Happy-path sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant D as Dispatch
    participant W as Work Order
    participant F as Workforce
    participant N as Notification

    C->>D: POST /assignments + Idempotency-Key
    D->>D: Atomically store key, fingerprint, PENDING assignment
    D->>W: Claim OPEN work order
    W-->>D: Location, skill, slot
    D->>F: Reserve inspector + slot
    F->>F: INSERT guarded by UNIQUE(inspector_id, slot)
    F-->>D: Reservation
    D->>W: Confirm owning assignment
    W-->>D: ASSIGNED
    D->>D: Mark CONFIRMED
    D->>N: Send with stable delivery key
    N-->>D: SENT
    D->>D: Store HTTP 201 response
    D-->>C: 201 same stored result on replay
```

## Failure path: notification unavailable

```mermaid
sequenceDiagram
    participant C as Client
    participant D as Dispatch
    participant N as Notification

    C->>D: Assignment request
    Note over D: Work Order and Workforce steps succeed
    D->>D: Mark assignment CONFIRMED
    loop At most 3 attempts
        D-xN: Send notification
        D->>D: Exponential backoff + jitter
    end
    D->>D: Keep notification PENDING
    D-->>C: 201 CONFIRMED, notification PENDING
    C->>D: POST /assignments/{id}/retry-notification
    D->>N: Same delivery key
    N-->>D: SENT (or idempotent replay)
    D-->>C: notification SENT
```

Notification is an after-commit side effect. Its failure does not undo operational work. A delivery committed before a lost response is repeated with the same delivery key and produces one record.

## Data ownership

```mermaid
erDiagram
    WORK_ORDER {
        string id PK
        string asset_id
        float longitude
        float latitude
        string required_skill
        datetime slot
        string state
        string assignment_id
    }
    GRIDFS_PHOTO {
        objectid id PK
        string work_order_id
        string filename
        string content_type
        long length
    }
    WORK_ORDER ||--o{ GRIDFS_PHOTO : owns

    INSPECTOR {
        string id PK
        json skills
        float min_longitude
        float min_latitude
        float max_longitude
        float max_latitude
    }
    RESERVATION {
        string id PK
        string inspector_id
        string assignment_id UK
        datetime slot
    }
    INSPECTOR ||--o{ RESERVATION : has

    ASSIGNMENT {
        string id PK
        string work_order_id
        string inspector_id
        string status
        string stage
        string reservation_id
        string notification_status
    }
    IDEMPOTENCY_RECORD {
        string key PK
        string fingerprint
        string assignment_id
        int status_code
        json response_body
    }
    ASSIGNMENT ||--|| IDEMPOTENCY_RECORD : replayed_by

    NOTIFICATION {
        string id PK
        string delivery_key UK
        string assignment_id
        string work_order_id
        string status
        int attempts
    }
```

These are separate service-owned models rather than one cross-service ER schema. IDs from other services are references only and have no database foreign keys.

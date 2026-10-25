# Dispatch downstream contracts

These contracts match the GeoInspect design reference and must be agreed with
the service owners when their implementations are integrated. Dispatch accesses
only these HTTP APIs and its own database.

All calls carry `X-Correlation-ID`. IDs are UUID strings, positions are longitude
and latitude in EPSG:4326, and `slot` is an ISO 8601 timestamp with timezone.
Errors should use `{"error":{"code":"...","message":"...","details":{}}}`.

## Work Order — Venkat

| POST path | Request JSON | Required success response |
| --- | --- | --- |
| `/api/v1/work-orders/{work_order_id}/claim` | `assignment_id` | Object with `required_skill`, `longitude`, `latitude`, and `slot` |
| `/api/v1/work-orders/{work_order_id}/confirm` | `assignment_id` | JSON object acknowledging the owning assignment |
| `/api/v1/work-orders/{work_order_id}/release-claim` | `assignment_id` | JSON object acknowledging the released claim |

Claim and confirmation must be safe to repeat with the same assignment ID after
an unknown outcome. A different assignment must not take an already-owned claim.
Release must affect only the matching owner and be safe to repeat after a lost
response. Return a definite 4xx for missing work orders or business conflicts.

## Workforce — Nia

`POST /api/v1/reservations` receives:

```json
{
  "assignment_id": "00000000-0000-4000-8000-000000000001",
  "inspector_id": "00000000-0000-4000-8000-000000000002",
  "required_skill": "ELECTRICAL",
  "longitude": 77.5946,
  "latitude": 12.9716,
  "slot": "2030-01-01T09:00:00+00:00"
}
```

Success returns a JSON object with reservation `id`. Repeating the same assignment
must return that same reservation. Workforce owns GIS/skill validation and atomic
inspector-slot uniqueness. Return HTTP 409 for an occupied slot or ineligible
inspector, and HTTP 404 for a missing inspector. Availability/discovery APIs are
Workforce-owned and can be added to Dispatch integration after their contract is
delivered; Dispatch currently assigns a selected inspector.

## Notification — Ujjawal

`POST /api/v1/notifications` receives `delivery_key`, `assignment_id`,
`work_order_id`, and `message`. Dispatch always derives the delivery key as
`assignment:{assignment_id}`, including manual retries.

Return a JSON object with `status: "SENT"` only after delivery is committed.
An in-progress attempt may return HTTP 202 with `status: "PROCESSING"`; Dispatch
keeps notification pending and retries within its configured bound. Delivery must
deduplicate by key, including concurrent requests and a committed-but-lost HTTP
response. HTTP 503 represents provider unavailability. Notification failure must
not invalidate a confirmed assignment.

## Unknown outcomes and integration checks

Transport failures, malformed JSON, and 5xx responses are treated as unresolved
outcomes. Dispatch keeps its saved assignment available for same-key recovery.
After all services are delivered, verify real HTTP happy path, claim/reservation
conflicts, simultaneous replay, lost responses, notification recovery, and one
reservation/delivery per assignment. Test doubles alone do not prove cross-service
database concurrency or actual delivery behavior.

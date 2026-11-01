# GeoInspect Kubernetes Workflow Evidence

## Objective

Verify that the GeoInspect core assignment workflow executes through the
Minikube/Kubernetes deployment rather than merely demonstrating running
pods.

## Deployed Components

The demonstrated Kubernetes environment contains:

- Work Order service
- Workforce service
- Dispatch service
- MongoDB
- PostgreSQL

Kubernetes Services provide stable DNS-based communication between the
application components.

## Workflow

The demonstrated flow is:

1. Create a Work Order through the Kubernetes Work Order service.
2. Create an eligible ELECTRICAL inspector through the Kubernetes
   Workforce service.
3. Verify the inspector is eligible based on:
   - required skill
   - GIS/service-area coverage
   - requested-slot availability
4. Submit an assignment through the Kubernetes Dispatch service.
5. Dispatch claims the Work Order.
6. Dispatch reserves the inspector through Workforce.
7. Dispatch confirms the Work Order.
8. The assignment reaches `CONFIRMED`.
9. Workforce availability changes from `true` to `false`.

## Verified Assignment Result

The demonstrated assignment reached:

- `status = CONFIRMED`
- `stage = CONFIRMED`
- a persisted `reservation_id`
- `notification_status = PENDING`

## Notification Integration Note

The current team integration snapshot does not contain the Notification
service.

The existing Dispatch design treats notification delivery separately from
the authoritative assignment transaction. Therefore, the successfully
confirmed assignment is preserved while notification remains `PENDING`.

No mock or fake Notification implementation was added solely for the
Kubernetes demonstration.

## Result

Core Kubernetes assignment workflow: PASS

Work Order confirmation: PASS

Workforce reservation: PASS

Cross-service Kubernetes communication: PASS

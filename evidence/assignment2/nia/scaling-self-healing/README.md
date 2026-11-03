# Kubernetes Scaling and Self-Healing Evidence

## Objective

Demonstrate Kubernetes replica scaling and automatic recovery for the
GeoInspect Workforce service.

## Scaling Demonstration

The Workforce Deployment was scaled from one replica to three replicas.

Verification:

- Desired replicas: 3
- Ready replicas: 3
- Available replicas: 3
- All Workforce pods reached `1/1 Running`

The final replica state is recorded in `scaling.txt`.

## Self-Healing Demonstration

After reaching three healthy replicas, one running Workforce pod was
manually deleted.

Kubernetes automatically created a replacement pod because the Workforce
Deployment declared a desired replica count of three.

After recovery:

- Workforce returned to 3/3 ready replicas.
- All replacement/current pods reached `Running`.
- The Workforce `/health` endpoint continued returning `UP`.

This demonstrates Kubernetes self-healing through Deployment-managed
replica reconciliation.

## Application Safety

Workforce reservation consistency remains database-backed. Multiple
Workforce replicas share PostgreSQL as the authoritative persistence layer.

The existing database-level inspector/slot uniqueness rule remains the
consistency boundary for reservation writes.

## Result

Scaling: PASS

Self-healing: PASS

Service recovery: PASS

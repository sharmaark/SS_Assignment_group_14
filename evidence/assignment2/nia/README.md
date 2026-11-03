# Nia — Assignment 2 Advanced Deployment Evidence

## Scope

This folder contains evidence for Nia's Assignment 2 deployment
contribution and optional advanced-task implementation.

## Advanced Task

The advanced implementation targets:

1. Minikube/Kubernetes deployment
2. Kubernetes scaling and self-healing

## Kubernetes Deployment

Nia created and integrated Kubernetes configuration for:

- GeoInspect namespace
- PostgreSQL
- MongoDB
- Workforce
- Work Order
- Dispatch

The deployment uses Kubernetes Services for internal service discovery.

Examples:

- `postgres:5432`
- `mongodb:27017`
- `work-order:8001`
- `workforce:8002`
- `dispatch:8003`

## Main Workflow

The demonstrated Kubernetes workflow includes:

`Work Order → Dispatch → Workforce → Work Order confirmation`

The workflow produced:

- confirmed Dispatch assignment
- persisted Workforce reservation
- confirmed Work Order
- inspector availability transition from `true` to `false`

The current team snapshot does not include the Notification service.
Dispatch preserves the confirmed assignment while notification delivery
remains `PENDING`.

## Scaling

Workforce was scaled from:

`1 replica → 3 replicas`

All three replicas reached `Running` and `Ready`.

## Self-Healing

One running Workforce pod was manually deleted.

Kubernetes automatically created a replacement and restored the desired
replica count to three.

The Workforce service remained operational after recovery.

## Evidence

### Kubernetes

See:

`kubernetes/`

Contains:

- node status
- deployments
- pods
- Kubernetes Services

### Workflow

See:

`workflow/`

Contains:

- confirmed Dispatch assignment
- post-assignment Work Order state
- post-reservation Workforce availability
- workflow explanation

### Scaling and Self-Healing

See:

`scaling-self-healing/`

Contains:

- three-replica deployment evidence
- scaling/self-healing explanation

## Result

Minikube/Kubernetes deployment: DEMONSTRATED

Core application workflow through Kubernetes: PASS

Workforce scaling: PASS

Workforce self-healing: PASS

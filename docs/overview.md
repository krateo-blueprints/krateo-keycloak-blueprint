---
type: Architecture
title: keycloak-blueprint — overview
description: What the blueprint renders and how it is built — the operator-for-lifecycle / KOG-for-config split, the two database providers, and how the Krateo composition maps down to Keycloak Operator and CloudNativePG CRs.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [blueprint, keycloak, cloudnativepg, operator, architecture]
timestamp: 2026-08-11T00:00:00Z
---

# Overview

`krateo-keycloak-blueprint` deploys a Keycloak server through the **official Keycloak
Operator**, and registers itself with Krateo as a `CompositionDefinition`. Two design
decisions define it.

**Operator for lifecycle, KOG for config.** This blueprint owns the server's
*lifecycle* — it renders a `Keycloak` CR (`k8s.keycloak.org/v2alpha1`) and its Postgres
backing store, and the operator reconciles them into a running StatefulSet, Service and
ingress. It does **not** touch the server's *configuration* — realms, clients, protocol
mappers, groups — which are managed separately, as their own Kubernetes CRs, by the
sibling `krateo-keycloak-operator-kog`. Keeping two systems from owning the same realm
is deliberate; the two connect at exactly one point, a bearer-token Secret the KOG uses
to call the server this blueprint stands up (see `docs/ARCHITECTURE.md`).

**It bundles neither operator.** The Keycloak Operator + its CRDs are cluster-scoped and
installed once, independent of any single server instance; with the default database
provider the CloudNativePG operator is likewise a one-time cluster prerequisite. The
chart renders only the *instance-level* resources — the `Keycloak` CR, the CNPG
`Cluster`, the Secrets — never the operators themselves (`operator.install` is `false`
by default and left as a convenience flag). See [usage](./usage.md) for the one-time
prerequisite install.

## What the chart renders

One composition (or one `helm install`) renders these manifests (`chart/templates/`):

| manifest | kind | apiVersion | role |
|---|---|---|---|
| `keycloak.yaml` | `Keycloak` | `k8s.keycloak.org/v2alpha1` | the server instance the operator reconciles: instances, hostname, DB wiring, http/TLS, ingress, proxy headers, bootstrap admin |
| `cluster-cnpg.yaml` | `Cluster` | `postgresql.cnpg.io/v1` | the CloudNativePG database — rendered **only** when `db.provider: cloudnativepg` |
| `secrets.yaml` | `Secret` (×1–2) | `v1` | the bootstrap-admin Secret, and (external mode only) the DB credentials Secret |

## The two database providers

Keycloak needs a Postgres. The `db.provider` value picks how it is provided:

- **`cloudnativepg` (default).** The chart renders a CloudNativePG `Cluster` named
  `db.cloudnativepg.clusterName` (default `keycloak-db`). CNPG provisions the Postgres,
  the `keycloak` database + owner role, and publishes a `<cluster>-app` credentials
  Secret and a `<cluster>-rw` read-write Service. The `Keycloak` CR's `spec.db` is wired
  to `<cluster>-rw` and the `<cluster>-app` Secret automatically
  (`templates/keycloak.yaml`) — no credentials to hand-carry. The CNPG operator must be
  installed cluster-wide. Validated end-to-end on kind with CNPG 1.29.1 + Keycloak
  26.6.3.
- **`external`.** Bring your own reachable Postgres. `spec.db.host`/`port` point at
  `db.host`/`db.port`, and the credentials come from `db.secret`. With
  `db.secret.create: true` the chart renders a dev-only credentials Secret from the
  literal `username`/`password`; in production set `create: false` and reference an
  existing Secret (for example one synced by External Secrets Operator).

## How the composition maps down

Applying the composition CR (`composition.krateo.io/v1alpha1`, kind `Keycloak`) makes
core-provider install the chart, which renders the operator-level resources:

```
Keycloak (composition.krateo.io/v1alpha1)     ← you apply this (samples/keycloak.yaml)
  └─ helm chart render
       ├─ Keycloak (k8s.keycloak.org/v2alpha1) ← the operator reconciles the server
       │    ├─ db.host: keycloak-db-rw          (cloudnativepg mode)
       │    └─ db credentials: keycloak-db-app  (cloudnativepg mode)
       ├─ Cluster (postgresql.cnpg.io/v1)       ← CNPG provisions Postgres (cloudnativepg mode)
       └─ Secret keycloak-bootstrap-admin       ← first-login admin, for creating the KOG client
```

The generated composition kind (`Keycloak`) and apiVersion
(`composition.krateo.io/v1alpha1`) are derived by core-provider from `chart/Chart.yaml`
— the chart `name` (`keycloak`) becomes the Kind, the chart `version` (`0.1.0`) the
apiVersion group version. See [api](./api.md) for the full CRD surface.

## Bootstrap admin and the hand-off

`bootstrapAdmin` renders a temporary admin Secret (`keycloak-bootstrap-admin`) and wires
it into the `Keycloak` CR's `spec.bootstrapAdmin`. That first admin exists so a human —
or, circularly, a one-off KOG CR against the master realm — can create the confidential
`krateo-kog` service-account client the config KOG needs, then hand its client secret to
`krateo-keycloak-operator-kog`. From there the KOG manages realms/clients/mappers
declaratively. The full SSO chain (Krateo portal + OpenStack Horizon riding one shared
Keycloak session) is laid out in `docs/ARCHITECTURE.md` and walked end-to-end in
`QUICKSTART.md`.

## Known constraint: operator startup probe on constrained nodes

On memory-constrained nodes the operator's Quarkus pod can fail its default
`startupProbe` (`/q/health/started`) before the JVM finishes booting, and
CrashLoopBackOff. If `keycloak-operator` won't reach Ready, relax the probe's
`failureThreshold` — the exact patch is in [usage](./usage.md) and the README. This is an
operator-install concern, not a chart-rendered resource.

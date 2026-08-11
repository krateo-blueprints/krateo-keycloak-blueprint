---
type: Configuration
title: keycloak-blueprint — configuration
description: The whole values.yaml surface — the Keycloak server, the two db.provider modes (cloudnativepg / external), the bootstrap admin, the operator flag — fully typed by values.schema.json, with the invariants that must hold.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [blueprint, keycloak, values, cloudnativepg, configuration]
timestamp: 2026-08-11T00:00:00Z
---

# Configuration

Everything is `chart/values.yaml`, fully typed by `chart/values.schema.json`. In the
Krateo path those same values are the `spec` of the `Keycloak` composition CR
(core-provider derives the CRD schema from `values.schema.json`), so the tables below
double as the CR field reference.

## The Keycloak server (`keycloak.*`)

| key | default | effect |
|---|---|---|
| `keycloak.name` | `keycloak` | name of the rendered `Keycloak` operator CR. |
| `keycloak.instances` | `1` | server replicas (`spec.instances`). Schema-required, `minimum: 1`. |
| `keycloak.hostname` | `keycloak.example.com` | the external hostname users and the OIDC clients reach (`spec.hostname.hostname`). **Must be a stable HTTPS host** — federation is very hostname-sensitive. Schema-required. |
| `keycloak.image` | `""` | pin a specific Keycloak image; empty uses the operator's pinned default. |
| `keycloak.http.httpEnabled` | `true` | allow plain HTTP (`spec.http.httpEnabled`). Set `true` when an ingress/Gateway terminates TLS upstream. |
| `keycloak.http.tlsSecretName` | `""` | a cert Secret to terminate TLS **at** Keycloak (`spec.http.tlsSecret`). Leave empty when TLS is terminated in front. |
| `keycloak.ingress.enabled` | `true` | render the operator-managed ingress (`spec.ingress.enabled`). |
| `keycloak.ingress.className` | `""` | ingress class; empty uses the cluster default. |
| `keycloak.proxyHeaders` | `xforwarded` | proxy header mode when TLS is terminated in front (`spec.proxy.headers`). Schema enum: `""`, `forwarded`, `xforwarded`. |
| `keycloak.additionalOptions` | `[]` | extra Keycloak options rendered into `spec.additionalOptions` as `{name, value}` pairs — e.g. `{name: hostname-strict, value: "false"}` or `{name: metrics-enabled, value: "true"}`. |

## Database (`db.*`)

| key | default | effect |
|---|---|---|
| `db.vendor` | `postgres` | the DB vendor (`spec.db.vendor`). Schema-required. |
| `db.database` | `keycloak` | the database name. In cloudnativepg mode CNPG bootstraps it. Schema-required. |
| `db.provider` | `cloudnativepg` | how Postgres is provided. Schema enum: `cloudnativepg`, `external`. Schema-required. |

### `cloudnativepg` mode (`db.cloudnativepg.*`)

Rendered as a `postgresql.cnpg.io/v1` `Cluster` (`templates/cluster-cnpg.yaml`); the
`Keycloak` CR is wired to the `<cluster>-rw` Service and `<cluster>-app` Secret CNPG
publishes.

| key | default | effect |
|---|---|---|
| `db.cloudnativepg.clusterName` | `keycloak-db` | the `Cluster` name; drives the `<name>-rw` Service and `<name>-app` Secret the `Keycloak` CR consumes. Schema-required. |
| `db.cloudnativepg.instances` | `1` | Postgres replicas. **`>=3` for HA in production.** Schema-required, `minimum: 1`. |
| `db.cloudnativepg.owner` | `keycloak` | role that owns the database; also the `-app` Secret username. Schema-required. |
| `db.cloudnativepg.imageName` | `""` | pin a Postgres image (e.g. `ghcr.io/cloudnative-pg/postgresql:17`); empty uses the CNPG default. |
| `db.cloudnativepg.storage.size` | `1Gi` | PVC size. |
| `db.cloudnativepg.storage.storageClass` | `""` | storage class; empty uses the cluster default. |

### `external` mode (`db.host`, `db.port`, `db.secret.*`)

Bring your own reachable Postgres. `spec.db.host`/`port` point at these; credentials come
from `db.secret`.

| key | default | effect |
|---|---|---|
| `db.host` | `keycloak-postgres` | the external Postgres host. |
| `db.port` | `5432` | the external Postgres port. |
| `db.secret.create` | `true` | render a credentials Secret from the literals below. **Dev only** — set `false` in production and reference an existing/ESO-synced Secret. |
| `db.secret.name` | `keycloak-db` | the credentials Secret name. Schema-required. |
| `db.secret.usernameKey` / `.passwordKey` | `username` / `password` | keys within the Secret the `Keycloak` CR reads. Schema-required. |
| `db.secret.username` / `.password` | `keycloak` / `change-me` | literals written when `create: true`. **Override `password`** — the chart NOTES warn on the `change-me` default. |

## Bootstrap admin (`bootstrapAdmin.*`)

A temporary admin for first login and creating the KOG service-account client.

| key | default | effect |
|---|---|---|
| `bootstrapAdmin.enabled` | `true` | wire `spec.bootstrapAdmin.user.secret` into the `Keycloak` CR. |
| `bootstrapAdmin.secret.create` | `true` | render the admin Secret from the literals below. Set `false` to reference an existing one. |
| `bootstrapAdmin.secret.name` | `keycloak-bootstrap-admin` | the admin Secret name. Schema-required. |
| `bootstrapAdmin.secret.username` / `.password` | `admin` / `change-me` | literals written when `create: true`. **Override `password`** — the chart NOTES warn on `change-me`. |

## Operator (`operator.*`)

| key | default | effect |
|---|---|---|
| `operator.install` | `false` | convenience flag to install the Keycloak Operator + CRDs with this release. Default `false`: the operator is normally a cluster-wide prerequisite ([usage](./usage.md)). |
| `operator.version` | `26.0.0` | the operator release these prerequisite URLs target. |

## Invariants

- **`keycloak.hostname` must be stable and HTTPS in any federated deployment.** OIDC
  federation (Krateo `authn`, Keystone/Horizon) is hostname-sensitive; a token minted
  against one host fails elsewhere.
- **Set `hostname-strict=false` when in-cluster callers use the Service name.** Add it
  via `keycloak.additionalOptions` so the config KOG can reach the server by its
  in-cluster Service rather than the public hostname.
- **In `cloudnativepg` mode the CNPG operator must be installed.** The chart renders the
  `Cluster` CR but not the operator that reconciles it; without CNPG the credentials
  Secret and `-rw` Service the `Keycloak` CR references are never created.
- **Never ship the `change-me` password defaults.** `db.secret.password` (external mode)
  and `bootstrapAdmin.secret.password` default to `change-me`; the chart's `NOTES.txt`
  warns, but override them (or reference an existing Secret with `create: false`).
- **`db.provider` picks exactly one backing store.** `cloudnativepg` renders the
  `Cluster` and ignores `db.host`/`db.secret`; `external` uses `db.host`/`db.secret` and
  renders no `Cluster`.

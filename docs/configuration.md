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
| `keycloak.instances` | `1` | server replicas (`spec.instances`). Schema-checked `minimum: 1`; optional (defaulted), so a Composition CR may omit it. |
| `keycloak.hostname` | `https://keycloak.example.com` | the external base URL users and the OIDC clients reach (`spec.hostname.hostname`). **A full `https://` URL** — Keycloak builds the token issuer from it, so the scheme never depends on proxy headers. Schema-checked (`^https://`); optional (defaulted), so a Composition CR may omit it. |
| `keycloak.image` | `""` | pin a specific Keycloak image; empty uses the operator's pinned default. |
| `keycloak.http.httpEnabled` | `true` | allow plain HTTP (`spec.http.httpEnabled`). Set `true` when an ingress/Gateway terminates TLS upstream. |
| `keycloak.http.tlsSecretName` | `""` | a cert Secret to terminate TLS **at** Keycloak (`spec.http.tlsSecret`). Leave empty when TLS is terminated in front. |
| `keycloak.http.relativePath` | `""` | serve Keycloak under a path prefix (Keycloak's `http-relative-path`, rendered into `spec.additionalOptions`), e.g. `/keycloak`, for a gateway that exposes several components on one host at per-component paths. Starts with `/`, no trailing slash; `keycloak.hostname` must end with the same path (the render refuses otherwise), and setting `http-relative-path` through `additionalOptions` is refused. |
| `keycloak.http.certificate.enabled` | `false` | have cert-manager issue Keycloak's serving certificate into `tlsSecretName` (which must then be set). DNS names: `<keycloak.name>-service.<namespace>.svc` and `.svc.cluster.local`, plus `extraDnsNames`; usages of a server leaf; ECDSA P-256, key rotated on renewal. |
| `keycloak.http.certificate.issuerRef.{kind,name}` | `ClusterIssuer` / `krateo-private-ca` | the issuer, e.g. [krateo-private-ca](https://github.com/krateo-blueprints/krateo-private-ca), whose issuance policy must allow those names from this namespace. |
| `keycloak.http.certificate.extraDnsNames` | `[]` | additional DNS names. |
| `keycloak.http.certificate.duration` | `""` | certificate lifetime; set it when the issuer's policy bounds the duration. |
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
| `db.secret.username` | `keycloak` | the username written when `create: true`. |
| `db.secret.password` | `""` | the external database's password, written when `create: true`. **Required** in that case: an empty value or `change-me` makes the render fail, because the password must match your database and cannot be generated. Use `create: false` with your own Secret to keep it out of values entirely. |

## Bootstrap admin (`bootstrapAdmin.*`)

A temporary admin for first login and creating the KOG service-account client.

| key | default | effect |
|---|---|---|
| `bootstrapAdmin.enabled` | `true` | wire `spec.bootstrapAdmin.user.secret` into the `Keycloak` CR. |
| `bootstrapAdmin.secret.create` | `true` | render the admin Secret from the literals below. Set `false` to reference an existing one. |
| `bootstrapAdmin.secret.name` | `keycloak-bootstrap-admin` | the admin Secret name. Schema-required. |
| `bootstrapAdmin.secret.username` | `admin` | the bootstrap user's name, written when `create: true`. This chart names the user, so it is never the operator's `temp-admin`. |
| `bootstrapAdmin.secret.password` | `""` (generated) | empty: the chart **generates** a 32-character password on first install and **reuses** the one already in the Secret on every upgrade. Set it only to choose one yourself. |
| `bootstrapAdmin.service.enabled` | `true` | also bootstrap an admin **service account** (a confidential client, `client_credentials`) via `spec.bootstrapAdmin.service.secret`. It is what keycloak-config-kog authenticates as, so the KOG's credential is never created by hand. |
| `bootstrapAdmin.service.secret.create` | `true` | render the service-account Secret (keys `client-id`, `client-secret`, the operator's names). Set `false` to reference an existing one. |
| `bootstrapAdmin.service.secret.name` | `keycloak-bootstrap-service` | the service-account Secret name. |
| `bootstrapAdmin.service.secret.clientId` | `krateo-bootstrap` | the client id in the master realm. |
| `bootstrapAdmin.service.secret.clientSecret` | `""` (generated) | empty: generated on first install and **reused** on every upgrade, by the same gated helper as the password. |

Both bootstrap accounts are **temporary** by Keycloak's own definition. The planned end state:
keycloak-config-kog uses the service account to create its permanent `krateo-kog` client and a
permanent human admin, switches to them, and deletes both bootstrap accounts. Until
keycloak-config-kog can authenticate with the service account directly, use it (or the user) to
create `krateo-kog` as described in [usage](./usage.md).

Read the password with
`kubectl get secret keycloak-bootstrap-admin -o jsonpath='{.data.password}' | base64 -d`.

**The operator applies the bootstrap admin only on the server's first start.** After that
the password lives in Keycloak's database, and changing the Secret changes nothing. That is
why the chart reuses the existing value instead of regenerating it (a regenerated Secret
would stop matching the live admin), and it is gated in CI by
`hack/check-bootstrap-password.py`.

**Installs first created with chart <= 0.2.0** that never set this value got the public
default `change-me`, and upgrading does not change a live password. The chart's NOTES print a
warning when the Secret still holds it. Change the admin password in the console.

## Operator (`operator.*`)

| key | default | effect |
|---|---|---|
| `operator.install` | `false` | convenience flag to install the Keycloak Operator + CRDs with this release. Default `false`: the operator is normally a cluster-wide prerequisite ([usage](./usage.md)). |
| `operator.version` | `26.0.0` | the operator release these prerequisite URLs target. |

## Invariants

- **`keycloak.hostname` is a stable `https://` URL.** OIDC federation (Krateo `authn`,
  Keystone/Horizon) is hostname-sensitive; a token minted against one issuer fails
  elsewhere. A bare host is refused by the schema: behind a TLS-terminating proxy that
  does not send `X-Forwarded-Proto`, it made Keycloak advertise an `http://` issuer.
- **A path prefix is set once, in `keycloak.http.relativePath`, and `hostname` carries it.** With
  `relativePath: /keycloak` and `hostname: https://portal.example.com/keycloak`, Keycloak serves only
  under `/keycloak` (the root answers 404), the issuer is `https://portal.example.com/keycloak/realms/<realm>`
  whatever path a request arrives on, and the operator moves its probes to `/keycloak/health/*` on the
  management port (measured on GKE with keycloak-operator 0.3.0 and Keycloak 26.6.3). Route
  `<prefix>/realms/` and `<prefix>/resources/` to the Service **without** rewriting the path; the admin
  console (`<prefix>/admin/`) is reached in-cluster and need not be exposed. In-cluster callers use the
  prefix too, e.g. keycloak-config-kog's `keycloak.baseUrl` `http://keycloak-service.<ns>.svc.cluster.local:8080/keycloak`.
- **Set `hostname-strict=false` when in-cluster callers use the Service name.** Add it
  via `keycloak.additionalOptions` so the config KOG can reach the server by its
  in-cluster Service rather than the public hostname.
- **In `cloudnativepg` mode the CNPG operator must be installed.** The chart renders the
  `Cluster` CR but not the operator that reconciles it; without CNPG the credentials
  Secret and `-rw` Service the `Keycloak` CR references are never created.
- **The external DB password is never defaulted.** With `db.provider: external` and
  `db.secret.create: true`, the render fails unless `db.secret.password` is set (and is not
  `change-me`). It must match your database, so the chart cannot generate it. Prefer
  `create: false` with an existing or ESO-synced Secret. The bootstrap admin password, by
  contrast, is generated (above).
- **`db.provider` picks exactly one backing store.** `cloudnativepg` renders the
  `Cluster` and ignores `db.host`/`db.secret`; `external` uses `db.host`/`db.secret` and
  renders no `Cluster`.

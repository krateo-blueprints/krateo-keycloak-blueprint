---
type: API
title: keycloak-blueprint — API
description: The Keycloak composition CRD this blueprint generates (composition.krateo.io/v1alpha1, kind Keycloak) and the downstream operator resources it renders — the Keycloak Operator CR, the CloudNativePG Cluster, and the Secrets.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [blueprint, keycloak, crd, compositiondefinition, api]
timestamp: 2026-08-11T00:00:00Z
---

# API

## The composition CRD this blueprint generates

Registering `compositiondefinition.yaml` makes core-provider generate a CRD and install
a controller for it. The generated API is derived from `chart/Chart.yaml`:

| derived from | value | result |
|---|---|---|
| chart `name` | `keycloak` | **Kind** `Keycloak` |
| chart `version` | `0.1.0` | **apiVersion** `composition.krateo.io/v1alpha1` |

The `CompositionDefinition` itself:

```yaml
apiVersion: core.krateo.io/v1alpha1
kind: CompositionDefinition
metadata:
  name: keycloak
  namespace: keycloak-system
spec:
  chart:
    url: oci://ghcr.io/krateo-blueprints/charts/keycloak
    version: "0.1.0"
```

An instance of the generated CRD (`composition.krateo.io/v1alpha1`, kind `Keycloak`) is
what you apply to stand up a server. Its `spec` is exactly the chart's `values.yaml`,
typed by `chart/values.schema.json`. A minimal instance (from `samples/keycloak.yaml`):

```yaml
apiVersion: composition.krateo.io/v1alpha1
kind: Keycloak
metadata:
  name: keycloak
  namespace: keycloak-system
spec:
  keycloak:
    name: keycloak
    instances: 1
    hostname: "keycloak.example.com"
    http:
      httpEnabled: true
    ingress:
      enabled: true
    proxyHeaders: "xforwarded"
  db:
    vendor: postgres
    database: keycloak
    provider: cloudnativepg
    cloudnativepg:
      clusterName: keycloak-db
      instances: 1
      owner: keycloak
      storage:
        size: 1Gi
  bootstrapAdmin:
    enabled: true
    secret:
      create: false
      name: keycloak-bootstrap-admin
```

The full `spec` field reference — every key, default, and constraint — is in
[configuration](./configuration.md); the constraints come from `values.schema.json`
(`keycloak`, `db` and their sub-objects carry `required` fields, `db.provider` and
`keycloak.proxyHeaders` are enums, `instances` fields have `minimum: 1`).

## Downstream resources the composition renders

Applying the composition CR renders these managed resources (`chart/templates/`):

### `Keycloak` — the operator CR

`k8s.keycloak.org/v2alpha1`, kind `Keycloak` (`templates/keycloak.yaml`). This is the
resource the **official Keycloak Operator** reconciles into a running server. Key spec
fields the chart sets:

| field | source | notes |
|---|---|---|
| `spec.instances` | `keycloak.instances` | server replicas |
| `spec.image` | `keycloak.image` | omitted when empty (operator default) |
| `spec.db.vendor` / `.database` | `db.vendor` / `db.database` | |
| `spec.db.host` / `.port` | `<cluster>-rw` : 5432 (cloudnativepg) or `db.host`/`db.port` (external) | wired by provider mode |
| `spec.db.usernameSecret` / `.passwordSecret` | `<cluster>-app` (cloudnativepg) or `db.secret` (external) | credentials reference |
| `spec.http.httpEnabled` / `.tlsSecret` | `keycloak.http.*` | `tlsSecret` omitted when empty |
| `spec.hostname.hostname` | `keycloak.hostname` | |
| `spec.ingress.enabled` / `.className` | `keycloak.ingress.*` | `className` omitted when empty |
| `spec.proxy.headers` | `keycloak.proxyHeaders` | proxy block omitted when empty |
| `spec.bootstrapAdmin.user.secret` | `bootstrapAdmin.secret.name` | rendered only when `bootstrapAdmin.enabled` |
| `spec.additionalOptions` | `keycloak.additionalOptions` | `{name, value}` list, omitted when empty |

### `Cluster` — the CloudNativePG database (cloudnativepg mode only)

`postgresql.cnpg.io/v1`, kind `Cluster` (`templates/cluster-cnpg.yaml`). Rendered only
when `db.provider: cloudnativepg`. Its `spec.bootstrap.initdb` creates `db.database`
owned by `db.cloudnativepg.owner`. CNPG then publishes, for a cluster named `<name>`:

- **Secret `<name>-app`** — keys `username`, `password`, `dbname`, `host`, `port`, `uri`
  — consumed by the `Keycloak` CR's `usernameSecret`/`passwordSecret`.
- **Service `<name>-rw`** — the read-write primary — consumed as the `Keycloak` CR's
  `db.host`.

The CNPG operator must be installed cluster-wide ([usage](./usage.md)).

### Secrets

`v1`, kind `Secret` (`templates/secrets.yaml`):

- **`keycloak-bootstrap-admin`** — the temporary first-login admin — rendered when
  `bootstrapAdmin.enabled` and `bootstrapAdmin.secret.create`.
- **the external-mode DB Secret** (`db.secret.name`) — rendered when
  `db.provider != cloudnativepg` and `db.secret.create` — dev convenience; in production
  set `create: false` and reference an existing/ESO-synced Secret. In cloudnativepg mode
  CNPG creates the credentials Secret, so the chart renders none.

## What the chart does not render

- **The operators** — the Keycloak Operator and (in cloudnativepg mode) the CNPG
  operator are cluster prerequisites installed once, not chart-rendered
  ([usage](./usage.md)). `operator.install` is a convenience flag defaulting to `false`.
- **Realms, clients, mappers, groups** — the server's *configuration* is managed as
  separate CRs by `krateo-keycloak-operator-kog` (`keycloak.ogen.krateo.io/v1alpha1`),
  not by this blueprint. See `docs/ARCHITECTURE.md` for the split and `QUICKSTART.md` for
  those CR shapes.

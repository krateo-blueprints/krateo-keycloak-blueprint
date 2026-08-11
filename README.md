# krateo-keycloak-blueprint

Krateo blueprint that deploys and manages a **Keycloak server** through the **official
Keycloak Operator** (`k8s.keycloak.org/v2alpha1`), backed by a CloudNativePG or external
Postgres. This is the **lifecycle** half of the Keycloak work; the **configuration** half
(realms, clients, mappers as CRs) is the sibling
[`krateo-keycloak-operator-kog`](https://github.com/krateo-blueprints/krateo-keycloak-operator-kog).

## What is this

A single Helm chart (`chart/`) plus the sibling `CompositionDefinition`
(`compositiondefinition.yaml`) that registers it with Krateo. Applying the resulting
`Keycloak` composition CR renders:

- a **`Keycloak` operator CR** — the server the official Keycloak Operator reconciles
  (instances, hostname, DB wiring, http/TLS, ingress, proxy headers, bootstrap admin);
- the **database**, per `db.provider`:
  - `cloudnativepg` (default) — a CloudNativePG `Cluster`; CNPG provisions the Postgres,
    the `keycloak` database + owner role, and the `<cluster>-app` credentials Secret +
    `<cluster>-rw` Service the `Keycloak` CR consumes;
  - `external` — bring your own reachable Postgres (a dev-convenience credentials Secret,
    or reference an existing one with `db.secret.create: false`);
- a bootstrap-admin **Secret** for first login and creating the KOG service-account client.

It deliberately bundles **neither operator** (Keycloak or CloudNativePG) — both are
one-time cluster prerequisites. The official Operator is chosen over Bitnami's chart,
which moved behind a paid subscription in Aug 2025 and ships unmaintained `bitnamilegacy`
images.

## Install

Install the prerequisite operators once, cluster-wide:

```bash
# Keycloak Operator (any keycloak-k8s-resources tag; matches operator.version)
VER=26.6.3
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/keycloaks.k8s.keycloak.org-v1.yml
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/keycloakrealmimports.k8s.keycloak.org-v1.yml
kubectl apply -n keycloak-system -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/kubernetes.yml

# CloudNativePG (default db.provider)
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.29/releases/cnpg-1.29.1.yaml
```

Then register the blueprint and apply a composition CR:

```bash
kubectl apply -f compositiondefinition.yaml
kubectl apply -f samples/keycloak.yaml
kubectl -n keycloak-system wait --for=condition=Ready keycloak/keycloak --timeout=5m
```

For a throwaway/CI run you can install the chart directly instead — see
[docs/usage.md](docs/usage.md).

> On memory-constrained nodes the operator's Quarkus pod can fail its default
> `startupProbe` and CrashLoopBackOff. If it won't reach Ready, relax the probe:
> `kubectl -n keycloak-system patch deploy keycloak-operator --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":30}]'`

## Configure

Everything is `chart/values.yaml`, fully typed by `chart/values.schema.json`. The
headline knobs:

| key | default | effect |
|---|---|---|
| `keycloak.hostname` | `keycloak.example.com` | the stable external HTTPS host the OIDC clients reach (federation is hostname-sensitive) |
| `keycloak.instances` | `1` | server replicas |
| `keycloak.http.httpEnabled` / `.tlsSecretName` | `true` / `""` | plain HTTP vs terminate TLS at Keycloak |
| `keycloak.ingress.enabled` / `.className` | `true` / `""` | operator-managed ingress |
| `keycloak.proxyHeaders` | `xforwarded` | proxy header mode when TLS terminates in front |
| `db.provider` | `cloudnativepg` | `cloudnativepg` (renders a CNPG `Cluster`) or `external` |
| `db.cloudnativepg.instances` | `1` | Postgres replicas (`>=3` for HA) |
| `bootstrapAdmin.enabled` | `true` | render the first-login admin Secret |

Set `hostname-strict=false` via `keycloak.additionalOptions` when in-cluster callers (like
the config KOG) reach the server by its Service name. The full surface and invariants are in
[docs/configuration.md](docs/configuration.md).

## Examples

- [examples/minimal-server](examples/minimal-server/README.md) — the smallest complete
  deployment: one Keycloak instance on CloudNativePG, via the Krateo composition or a
  direct `helm install`.

The full end-to-end SSO chain (Krateo portal + OpenStack Horizon on one shared Keycloak
session) is walked in [QUICKSTART.md](QUICKSTART.md).

## Docs

- [docs/index.md](docs/index.md) — the map of the doc bundle
- [docs/overview.md](docs/overview.md) — architecture: the lifecycle/config split, the two db providers, how the composition maps to operator CRs
- [docs/usage.md](docs/usage.md) — install the operators, register and apply, hand off to the KOG
- [docs/configuration.md](docs/configuration.md) — the whole `values.yaml` surface + invariants
- [docs/api.md](docs/api.md) — the composition CRD and the downstream operator resources
- [docs/examples.md](docs/examples.md) — the runnable examples
- [docs/release.md](docs/release.md) — how a release ships
- [docs/log.md](docs/log.md) — curated history
- [docs/llms.txt](docs/llms.txt) — the LLM doc index
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the wider Keycloak↔Krateo↔OpenStack SSO design

## Develop & release

The chart lives in `chart/`; register it with `compositiondefinition.yaml`. A release is a
single plain-semver tag (`X.Y.Z`, **no** `v` prefix) matching `chart/Chart.yaml`'s
`version`:

```bash
git tag X.Y.Z && git push origin X.Y.Z
```

`.github/workflows/release-chart.yaml` lints, verifies the tag matches `Chart.yaml`,
packages, and pushes to `oci://ghcr.io/krateo-blueprints/charts/keycloak` — exactly what
`compositiondefinition.yaml`'s `spec.chart.url` points at. After publishing, bump the
`CompositionDefinition`'s `spec.chart.version`. `.github/workflows/lint.yaml` runs the
shared `lint-docs` (Krateo Documentation Standard) check on every PR. Full runbook in
[docs/release.md](docs/release.md).

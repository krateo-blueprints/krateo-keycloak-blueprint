---
type: Component
title: keycloak-blueprint — index
description: The map of the krateo-keycloak-blueprint doc bundle — a Krateo blueprint that deploys and manages a Keycloak server through the official Keycloak Operator, with a CloudNativePG or external Postgres backing store.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [blueprint, keycloak, identity, sso, compositiondefinition]
timestamp: 2026-08-11T00:00:00Z
---

# keycloak-blueprint

`krateo-keycloak-blueprint` is a Krateo blueprint that deploys and manages a
**Keycloak server** through the **official Keycloak Operator**
(`k8s.keycloak.org/v2alpha1`). It ships one Helm chart (`chart/`) and the sibling
`CompositionDefinition` (`compositiondefinition.yaml`) that registers it with Krateo,
turning `values.yaml` into a typed `Keycloak` composition CR. Applying that CR renders
a `Keycloak` operator CR, its Postgres backing store, and a bootstrap-admin Secret —
one composition, one running identity server.

This is the **lifecycle** half of the Keycloak work: it stands the server up and keeps
it running. The **configuration** half — realms, clients, mappers and groups as
Kubernetes CRs — lives in the sibling `krateo-keycloak-operator-kog`. The blueprint
deliberately bundles neither operator (Keycloak or CloudNativePG); both are cluster
prerequisites installed once.

## The bundle (start here)

- [overview](./overview.md) — what the blueprint renders, the operator/KOG split, the
  two database providers, and how the composition maps to operator CRs.
- [usage](./usage.md) — install the prerequisite operators, deploy the server via the
  `CompositionDefinition` or raw Helm, and hand off to the config KOG.
- [configuration](./configuration.md) — the whole `values.yaml` surface: the server,
  the two `db.provider` modes, the bootstrap admin, and the invariants that must hold.
- [api](./api.md) — the `Keycloak` composition CRD the chart generates, and the
  downstream operator resources it produces.
- [examples](./examples.md) — the runnable example under `examples/`.
- [release](./release.md) — how a release ships (a plain-semver tag → the OCI chart).
- [log](./log.md) — curated history.
- [llms.txt](./llms.txt) — the doc index of this bundle.

## Layout

- `chart/` — the blueprint chart:
  - `templates/keycloak.yaml` — the `Keycloak` operator CR (instances, hostname, DB
    wiring, http/TLS, ingress, proxy headers, bootstrap admin).
  - `templates/cluster-cnpg.yaml` — the CloudNativePG `Cluster` CR, rendered only in
    `db.provider: cloudnativepg` mode.
  - `templates/secrets.yaml` — the external-mode DB credentials Secret (dev
    convenience) and the bootstrap-admin Secret.
  - `values.yaml` + `values.schema.json` — every value with rationale, fully typed so
    core-provider can derive the composition CRD.
- `compositiondefinition.yaml` — this component's own registration, pointing at the
  published OCI chart.
- `samples/keycloak.yaml` — a sample composition CR (`composition.krateo.io/v1alpha1`,
  kind `Keycloak`) to apply once the `CompositionDefinition` is registered.
- `examples/minimal-server/` — a runnable minimal deployment.
- `docs/ARCHITECTURE.md` + `QUICKSTART.md` — the wider Keycloak↔Krateo↔OpenStack SSO
  design and an end-to-end walkthrough.

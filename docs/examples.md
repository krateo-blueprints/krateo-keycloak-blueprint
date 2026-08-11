---
type: ExampleIndex
title: keycloak-blueprint — examples
description: Index of the runnable examples under examples/.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [examples, keycloak, blueprint]
timestamp: 2026-08-11T00:00:00Z
---

# Examples

- [examples/minimal-server](../examples/minimal-server/README.md) — the smallest
  complete deployment: one Keycloak instance backed by a CloudNativePG Postgres, with a
  bootstrap admin. Deploy it the Krateo way (register the `CompositionDefinition`, apply
  the `samples/keycloak.yaml` composition CR) or with a direct `helm install`. It doubles
  as the reference for the shape `samples/keycloak.yaml` produces, and notes how to vary
  it toward external Postgres or a production TLS/HA setup.

For the full end-to-end SSO chain (Krateo portal + OpenStack Horizon riding one shared
Keycloak session, with the config KOG provisioning realms/clients/mappers), see the
repo's `QUICKSTART.md` and `docs/ARCHITECTURE.md`.

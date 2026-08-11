---
type: Log
title: keycloak-blueprint — log
description: Curated chronological history of krateo-keycloak-blueprint — notable changes and decisions, not a generated changelog.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [log, history, keycloak]
timestamp: 2026-08-11T00:00:00Z
---

# Log

Curated history; release notes live in GitHub Releases.

## 2026-08-11 — Documentation Standard adoption

The repo adopts the Krateo Documentation Standard: the invariant `docs/` bundle
(`index`, `overview`, `usage`, `configuration`, `api`, `examples`, `release`, `log`,
`llms.txt`), a runnable `examples/minimal-server`, a rewritten `README.md` with the six
standard sections, and the shared `lint-docs` check wired in via
`.github/workflows/lint.yaml`. The pre-existing `docs/ARCHITECTURE.md` and `QUICKSTART.md`
are kept as the wider Keycloak↔Krateo↔OpenStack SSO design and end-to-end walkthrough.

## 0.1.0 — first release

The blueprint ships whole: the `keycloak` chart (the `Keycloak` operator CR, the
CloudNativePG `Cluster`, the DB and bootstrap-admin Secrets) and the sibling
`CompositionDefinition` that registers it with Krateo. Design decisions worth keeping:

- **Operator for lifecycle, KOG for config.** The blueprint owns the server's lifecycle
  and stops there; realms/clients/mappers are the sibling `krateo-keycloak-operator-kog`'s
  job, so two systems never own the same realm.
- **Official Operator, not Bitnami.** Bitnami's Keycloak chart/images moved behind a paid
  subscription in Aug 2025 and now ship unmaintained `bitnamilegacy` images; the official
  Operator is the upstream-maintained, CRD-driven path.
- **Two database providers.** `cloudnativepg` (default) provisions Postgres via a CNPG
  `Cluster` and auto-wires the `-rw` Service and `-app` Secret into the `Keycloak` CR;
  `external` brings your own reachable Postgres. Neither operator is bundled — both are
  one-time cluster prerequisites.

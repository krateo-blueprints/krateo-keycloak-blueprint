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

## 2026-11-08 — `keycloak.hostname` is a full https URL (breaking)

`keycloak.hostname` now takes a full base URL (`https://keycloak.example.com`) and the
schema refuses a bare host. The reason is that **the default must not depend on a proxy
header the chart does not control**; it is not that a bare host always fails. With a bare
host the scheme comes from `X-Forwarded-Proto`, so it is right only where the proxy sends
that header. Found on the gate 1 cluster: behind a TLS-terminating Gateway that sends no
`X-Forwarded-Proto`, Keycloak 26.6.3 advertised `http://keycloak.gate1.cmp.krateo.dev/realms/krateo`
even with `proxyHeaders: xforwarded`. The failure was **silent**: 200s, a valid
certificate, a working console. Only a consumer that validates the scheme
(selfservice's parent-SSO helper) noticed, so a deployment without one would carry an
http issuer indefinitely. That is why the schema enforces it rather than a docs note.

Verified on the same cluster with the URL form: all 13 URL-valued fields of
`/realms/krateo/.well-known/openid-configuration` are `https://keycloak.gate1.cmp.krateo.dev/…`,
with no other host and no port. The operator already accepts a URL here and derives the
Ingress host from it (`KeycloakIngressDependentResource`, `new URL(hostname).getHost()`,
Keycloak 26.6.3).

**Migration:** prefix the existing value with `https://`, e.g.
`keycloak.example.com` → `https://keycloak.example.com`. Nothing else changes.

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

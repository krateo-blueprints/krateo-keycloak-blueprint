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

## 2026-11-12 — 0.2.7: the CRD bridge survives `helm upgrade --reuse-values`

**keycloak-operator**: `helm upgrade --reuse-values` from 0.2.5 (or 0.2.4) to 0.2.6 failed with
`nil pointer evaluating interface {}.enabled`: reuse-values upgrades with the previous release's
values, which have no `crdOwnershipBridge`, and does not apply the new chart's defaults. Measured on GKE
while validating 0.3.0. The bridge template now reads the key with defaults (enabled, the same pinned
kubectl image). CI gate `hack/check-reuse-values.py` renders each chart with its values.yaml replaced
by a previous release's, the reuse-values shape, and requires the same objects as a default render.

## 2026-11-11 — 0.2.6: Keycloak's own serving certificate; CRD ownership bridge

**keycloak**: `keycloak.http.certificate` has cert-manager issue Keycloak's serving certificate into
`keycloak.http.tlsSecretName`. Measured on GKE with krateo-private-ca 0.1.0: the request was approved
by the CA's issuance policy, Keycloak served TLS on 8443 with it, and a client in another namespace
that trusts only the published CA bundle got HTTP 200 with verification OK (issuer
`https://keycloak-service.<ns>.svc.cluster.local:8443/realms/master`); the system trust store was
refused.

**keycloak-operator**: a post-install/post-upgrade Job stamps the release's Helm ownership on the two
CRDs installed from `crds/`, so the release that renders them from `templates/` (0.3.0) can adopt
them. Measured: 0.2.4 → templates/ directly fails with `invalid ownership metadata`; 0.2.4 → 0.2.6
stamps both CRDs; 0.2.6 → templates/ adopts them (both in the release manifest, `keep`). A cluster
must run 0.2.6 before 0.3.0.

Also from 0.2.5 (2026-11-11): no `values.schema.json` key that `values.yaml` defaults is `required`,
gated in lint.

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

---
type: Runbook
title: keycloak-blueprint — release
description: How a release ships — a plain-semver tag matching Chart.yaml drives the chart to the GHCR OCI registry via release-chart.yaml, and the CompositionDefinition is bumped to the published version.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [release, oci, ghcr, helm]
timestamp: 2026-08-11T00:00:00Z
---

# Release

One plain-semver tag (`X.Y.Z`, **no** `v` prefix) releases the chart. The tag must match
`chart/Chart.yaml`'s `version` — the workflow enforces it.

## What a tag ships

`.github/workflows/release-chart.yaml` triggers on a `X.Y.Z` tag (or manual dispatch)
and:

1. `helm lint chart` — validates the chart and its `values.schema.json`.
2. **Verifies the git tag equals `chart/Chart.yaml`'s `version`** — a mismatch fails the
   release, so the published artifact's version and the tag can never diverge.
3. `helm package chart` — packages the chart. `helm package` does not render templates,
   so a chart requiring runtime input (like this one) still publishes.
4. `helm push` to `oci://ghcr.io/<owner>/charts` — the owner namespace is derived from
   the repository owner (lowercased), with a retry loop for GHCR first-push flakiness.

The published artifact is `oci://ghcr.io/krateo-blueprints/charts/keycloak`, which is
exactly what `compositiondefinition.yaml`'s `spec.chart.url` points at.

## Steps

```console
$ git tag X.Y.Z && git push origin X.Y.Z
```

Then verify the workflow went green and the artifact exists:

```console
$ helm show chart oci://ghcr.io/krateo-blueprints/charts/keycloak --version X.Y.Z | head -3
```

After the chart is published, bump `compositiondefinition.yaml`'s `spec.chart.version`
to `X.Y.Z` on `main` — it is this component's own registration and must point at a
version that exists. Keep `chart/Chart.yaml`'s `version` in step (the release job checks
the tag against it).

## PR-time checks

`.github/workflows/lint.yaml` runs the shared `lint-docs` job (the Krateo Documentation
Standard) on every PR. `.github/workflows/security.yml` runs the shared security scan.

## Version pinning downstream

Consumers register the blueprint by an explicit `spec.chart.version`; nothing tracks a
mutable tag. The OCI chart tag is immutable — the release workflow publishes only the
semver tag, and the `CompositionDefinition` asks for exactly that version.

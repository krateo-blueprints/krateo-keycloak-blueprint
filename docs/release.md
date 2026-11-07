---
type: Runbook
title: keycloak-blueprint — release
description: How a release ships — a plain-semver tag stamps the version, pushes each changed chart to GHCR and publishes the same archives to the Marketplace index (keycloak to blueprints, keycloak-operator to operators).
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [release, oci, ghcr, helm]
timestamp: 2026-11-07T00:00:00Z
---

# Release

One plain-semver tag (`X.Y.Z`, **no** `v` prefix) releases the charts under `helm/`. The committed
`helm/*/Chart.yaml` and `compositiondefinition.yaml` carry the `CHART_VERSION` placeholder; the tag is
the only place a version is written.

## What a tag ships

`.github/workflows/release-tag.yaml` triggers on a `X.Y.Z` tag and publishes each chart twice, with the
same bytes, as the organisation's publishing standard requires
([krateo-blueprints/charts PUBLISHING.md](https://github.com/krateo-blueprints/charts/blob/main/PUBLISHING.md)):

1. **Refuses to start** unless the tagged commit has a successful `lint` run and the org secret
   `CHARTS_PUBLISH_TOKEN` is set, so nothing reaches GHCR that cannot also reach the Marketplace.
2. **Selects** the charts that changed since the previous semver tag (every chart when there is no
   previous tag or a change lies outside `helm/`).
3. **Stamps** `compositiondefinition.yaml` from the tag, refusing if the chart it installs (`keycloak`)
   is not in this release, and stamps each selected `Chart.yaml`.
4. **Packages and checks** each selected chart. The channel follows from the content: `keycloak` has a
   `values.schema.json` and a `CompositionDefinition`, so it is a blueprint, and the stamped
   `compositiondefinition.yaml` is copied into its root before `helm package`; the archive must then
   hold `compositiondefinition.yaml` (installing `oci://ghcr.io/krateo-blueprints/charts/keycloak` at
   the tag's version) and `values.schema.json`, and `Chart.yaml` must have an https `icon` and
   `keywords`. `keycloak-operator` has neither, so it is an operator.
5. **Pushes** each to `oci://ghcr.io/krateo-blueprints/charts/<chart>:X.Y.Z`, which for `keycloak` is
   exactly what `compositiondefinition.yaml`'s `spec.chart.url` points at.
6. **Publishes** the same archives to the Marketplace index through the organisation's publisher
   (`krateo-blueprints/charts/.github/workflows/publish-chart.yaml`, pinned per its rule 9): `keycloak` to
   `https://krateo-blueprints.github.io/charts/blueprints`, `keycloak-operator` to
   `https://krateo-blueprints.github.io/charts/operators`. A channel with no chart in this release is
   skipped. The portal Marketplace installs from these indexes, not from GHCR; the publisher succeeds
   only once the served index lists the version and `helm pull --repo` installs it anonymously.
7. **Attaches** the stamped `compositiondefinition.yaml` to the GitHub release for the tag.

## Steps

```console
$ git tag X.Y.Z && git push origin X.Y.Z
```

Then verify the workflow went green and both copies exist:

```console
$ helm show chart oci://ghcr.io/krateo-blueprints/charts/keycloak --version X.Y.Z | head -3
$ helm pull keycloak --version X.Y.Z --repo https://krateo-blueprints.github.io/charts/blueprints
```

Nothing is bumped by hand: apply the stamped `compositiondefinition.yaml` attached to the release (the
branch copy carries the placeholder).

## PR-time checks

`.github/workflows/lint.yaml` runs the shared `lint-docs` job (the Krateo Documentation
Standard) on every PR and on every push to `main`; the release requires its run on the tagged
commit. `.github/workflows/security.yml` runs the shared security scan.

## Version pinning downstream

Consumers register the blueprint by an explicit `spec.chart.version`; nothing tracks a
mutable tag. The OCI chart tag is immutable — the release workflow publishes only the
semver tag, and the stamped `CompositionDefinition` asks for exactly that version.

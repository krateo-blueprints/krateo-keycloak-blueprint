# Vendored upstream content

Everything here derives from **keycloak/keycloak-k8s-resources @ 26.6.3**:

    https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/26.6.3/kubernetes/

| file | upstream source | sha256 (upstream) |
|---|---|---|
| `crds/keycloaks.k8s.keycloak.org-v1.yml` | `keycloaks.k8s.keycloak.org-v1.yml` | `846783b8de418a5b…` |
| `crds/keycloakrealmimports.k8s.keycloak.org-v1.yml` | `keycloakrealmimports.k8s.keycloak.org-v1.yml` | `4b2220309a91f04e…` |
| `templates/operator.yaml` | `kubernetes.yml` + the delta below | — |

Both CRDs were verified **byte-identical** to upstream 26.6.3 on 2026-08-15.

## The only modifications to `kubernetes.yml`

1. `namespace: keycloak` (hardcoded upstream) → `namespace: {{ .Release.Namespace }}`,
   and an explicit `namespace:` added to namespaced objects that omitted it — so the
   operator installs wherever the release targets.
2. The JOSDK controller namespace env vars are driven from `.Values.watchNamespaces`
   instead of upstream's `JOSDK_WATCH_CURRENT` sentinel, making the watched namespace
   explicit rather than implicit in the release namespace.

Nothing else. Re-verify with:

    curl -sSL "$UPSTREAM/kubernetes.yml" | diff - templates/operator.yaml

and expect only namespace/env differences.

## Provenance note

Before 2026-08-15 this chart existed **only as a published artifact** at
`ghcr.io/braghettos/charts/keycloak-operator:26.6.3`, with no source repository in any
org — hand-pushed, vendoring third-party CRDs, and a dependency of every provisioned
child. It was reconstructed here after verifying its CRDs against upstream. Bump by
raising `appVersion`, re-fetching both CRDs at the new tag, and re-applying the two
modifications above.

---
type: Usage
title: keycloak-blueprint — usage
description: How to run the blueprint — install the prerequisite Keycloak and CloudNativePG operators once, register the CompositionDefinition and apply the composition (or install the chart directly), then hand off to the config KOG.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [blueprint, keycloak, install, cloudnativepg, kog]
timestamp: 2026-08-11T00:00:00Z
---

# Usage

## Prerequisites — install the operators once

The blueprint renders instance-level resources but bundles neither operator. Both are
cluster-scoped and installed once.

### Keycloak Operator

```console
$ VER=26.6.3   # any keycloak-k8s-resources tag; matches operator.version
$ kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/keycloaks.k8s.keycloak.org-v1.yml
$ kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/keycloakrealmimports.k8s.keycloak.org-v1.yml
$ kubectl apply -n keycloak-system -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$VER/kubernetes/kubernetes.yml
```

See <https://www.keycloak.org/operator/installation> for the exact per-release URLs.
Verified end-to-end on kind with operator 26.6.3.

### CloudNativePG (default `db.provider`)

With the default `db.provider: cloudnativepg`, the CNPG operator must also be installed
cluster-wide:

```console
$ kubectl apply --server-side -f \
    https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.29/releases/cnpg-1.29.1.yaml
```

Skip this only if you run `db.provider: external` against your own Postgres.

## Register the CompositionDefinition (the Krateo path)

Register the blueprint so Krateo can instantiate it. `compositiondefinition.yaml` points
`spec.chart.url` at the published OCI chart:

```console
$ kubectl apply -f compositiondefinition.yaml
```

core-provider installs a controller for the composition kind derived from the chart —
`Keycloak` in `composition.krateo.io/v1alpha1`. Then apply a composition CR (a copy of
`samples/keycloak.yaml`):

```console
$ kubectl apply -f samples/keycloak.yaml
```

That renders the `Keycloak` operator CR + (in cloudnativepg mode) the CNPG `Cluster` +
the bootstrap-admin Secret. Wait for the server:

```console
$ kubectl -n keycloak-system wait --for=condition=Ready keycloak/keycloak --timeout=5m
```

## Or install the chart directly (dev / CI)

For a throwaway or CI run you can `helm install` the chart without Krateo:

```console
$ helm install keycloak ./chart -n keycloak-system \
    --set keycloak.hostname=keycloak.demo.local \
    --set keycloak.http.httpEnabled=true \
    --set keycloak.ingress.enabled=false \
    --set-json 'keycloak.additionalOptions=[{"name":"hostname-strict","value":"false"}]'
```

`db.provider` defaults to `cloudnativepg`, so this also renders the `keycloak-db` CNPG
`Cluster` that provisions Postgres and the `keycloak-db-app` credentials.
`hostname-strict=false` lets in-cluster callers (like the config KOG) reach the server
by its Service name rather than the public hostname. See [configuration](./configuration.md)
for the full value surface.

## Operator startup probe on constrained nodes

If `keycloak-operator` CrashLoopBackOffs on a memory-constrained node (its Quarkus pod
fails the default `startupProbe` before the JVM boots), relax the probe:

```console
$ kubectl -n keycloak-system patch deploy keycloak-operator --type=json \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":30}]'
```

## Hand off to the config KOG

Once the server is Ready, wire up its configuration half:

1. Create a confidential **service-account client** `krateo-kog` (`serviceAccountsEnabled=true`)
   with the `realm-management` roles the config KOG needs (`manage-clients`,
   `manage-realm`, `manage-users`, …). The bootstrap admin can create it, or — nicely
   circular — a one-off `KeycloakClient` CR once the KOG is up against the master realm.
2. Put its client secret in the `keycloak-kog-client` Secret that
   `krateo-keycloak-operator-kog`'s ESO `Webhook` generator reads.
3. Point the config KOG's `keycloak.baseUrl` at this server's hostname (or its in-cluster
   Service when `hostname-strict=false`).

`QUICKSTART.md` walks the whole chain end-to-end, including the SSO realm/clients the
OpenStack Horizon federation needs.

## Uninstall

```console
$ helm -n keycloak-system uninstall keycloak     # also removes the CNPG Cluster
```

Or delete the composition CR if you deployed through Krateo. The operators, being
cluster prerequisites, are removed separately.

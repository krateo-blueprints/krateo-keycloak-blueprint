---
type: Example
title: minimal-server — a Keycloak server on CloudNativePG
description: A minimal end-to-end deployment of the keycloak blueprint — one Keycloak instance backed by a CloudNativePG Postgres, deployed either via the Krateo composition or a direct helm install.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak
tags: [example, keycloak, cloudnativepg, blueprint]
timestamp: 2026-08-11T00:00:00Z
---

# minimal-server

The smallest complete deployment this blueprint produces: **one Keycloak instance**
backed by a **CloudNativePG** Postgres, with a bootstrap admin. It is the shape of
`samples/keycloak.yaml` — apply it the Krateo way (a composition CR) or install the chart
directly for a throwaway/CI run.

## Prerequisites

Both operators must already be installed cluster-wide ([usage](../../docs/usage.md)):

- the **Keycloak Operator** (`k8s.keycloak.org/v2alpha1` CRDs + Deployment)
- **CloudNativePG** (the default `db.provider`)

```console
$ kubectl create namespace keycloak-system
```

## Deploy via the Krateo composition

Register the blueprint, then apply a composition CR:

```console
$ kubectl apply -f ../../compositiondefinition.yaml
$ kubectl apply -f ../../samples/keycloak.yaml
```

`samples/keycloak.yaml` is a `composition.krateo.io/v1alpha1` `Keycloak` with
`db.provider: cloudnativepg`, one server instance, and one Postgres instance. core-provider
installs the chart, which renders the `Keycloak` operator CR, the `keycloak-db` CNPG
`Cluster`, and (with `create: true`) the bootstrap-admin Secret.

## Or install the chart directly

```console
$ helm install keycloak ../../chart -n keycloak-system \
    --set keycloak.hostname=keycloak.demo.local \
    --set keycloak.http.httpEnabled=true \
    --set keycloak.ingress.enabled=false \
    --set-json 'keycloak.additionalOptions=[{"name":"hostname-strict","value":"false"}]'
```

`db.provider` defaults to `cloudnativepg`, so this also renders the `keycloak-db` CNPG
`Cluster`; `hostname-strict=false` lets in-cluster callers reach the server by its Service
name. Wait for the server:

```console
$ kubectl -n keycloak-system wait --for=condition=Ready keycloak/keycloak --timeout=5m
```

## Verify

```console
$ kubectl -n keycloak-system get keycloak,cluster.postgresql.cnpg.io,secret
```

You should see the `Keycloak` CR, the `keycloak-db` CNPG `Cluster` (with its
`keycloak-db-app` Secret and `keycloak-db-rw` Service), and the
`keycloak-bootstrap-admin` Secret. From here, follow the config-KOG hand-off in
[usage](../../docs/usage.md) and the full SSO chain in `../../QUICKSTART.md`.

## Vary it

- **External Postgres** — set `db.provider: external`, `db.host`, and reference an
  existing credentials Secret (`db.secret.create: false`); no CNPG `Cluster` is rendered.
- **Production TLS** — set `keycloak.ingress.enabled: true`, a real HTTPS
  `keycloak.hostname`, and `db.cloudnativepg.instances: 3` for an HA database.

See [configuration](../../docs/configuration.md) for the full value surface.

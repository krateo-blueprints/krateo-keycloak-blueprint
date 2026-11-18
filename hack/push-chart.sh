#!/usr/bin/env bash
# Push one packaged chart to an OCI registry, surviving GHCR's read-after-write race on the tag step and nothing else.
#
#   hack/push-chart.sh CHART.tgz oci://REGISTRY/PATH
#
# The race (observed twice: the keycloak KOG 0.11.0 release, and this repository's first prerelease.yaml run,
# 44279368853, 2026-11-18). `helm push` (oras-go ExtendedCopy) PUTs the manifest by digest, then tags it, and the tag
# step first GETs that manifest by digest. GHCR answered that GET 404 about one second after accepting the PUT, so helm
# exits with
#     Error: failed to perform "Tag" on destination: sha256:<digest>: not found
# and leaves an untagged manifest behind. Measured for run 44279368853: the GHCR versions API listed exactly one
# version of charts/rabbitmq-cluster-operator, the untagged sha256:64960ed5..., created 09:48:36Z, the second helm
# failed; a GET of that digest returned 200 a minute later.
#
# On that exact error only, this script polls until the registry serves the manifest at that digest (bounded:
# PUSH_POLL_ATTEMPTS x PUSH_POLL_INTERVAL seconds, default 10 x 3), then pushes the SAME archive again. The second
# push has the same manifest digest: helm 4 builds the manifest from the archive bytes, Chart.yaml and the archive's
# modification time (pkg/pusher/ocipusher.go PushOptCreationTime), none of which changed, so its PUT is idempotent and
# its tag lands on the digest already there. The script checks that: a second push reporting another digest fails.
# Any other push error fails at once, unretried; a digest still unfetchable after the bound fails, saying so.
#
# Reading the manifest uses the registry's own token challenge (WWW-Authenticate: Bearer realm=...), with
# REGISTRY_USER and REGISTRY_TOKEN as credentials when set (anonymous otherwise), and checks the body hashes to the
# digest. hack/validate-push-chart.py drives this script with stand-in helm and curl.
set -euo pipefail

die() { echo "::error::$*" >&2; exit 1; }

tgz="${1:-}" repo="${2:-}"
[ -f "$tgz" ] || die "usage: $0 CHART.tgz oci://REGISTRY/PATH (no archive at '${tgz}')"
[[ "$repo" == oci://*/* ]] || die "usage: $0 CHART.tgz oci://REGISTRY/PATH (got '${repo}')"
attempts="${PUSH_POLL_ATTEMPTS:-10}" interval="${PUSH_POLL_INTERVAL:-3}"

name="$(tar -tzf "$tgz" | head -n1 | cut -d/ -f1)"
[ -n "$name" ] || die "${tgz} has no top-level chart directory"
host="${repo#oci://}"; path="${host#*/}/${name}"; host="${host%%/*}"

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

RACE='failed to perform "Tag" on destination: sha256:[0-9a-f]{64}: not found'

sha256_of() {
  if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# 0 when the registry serves a manifest whose bytes hash to $1.
fetchable() {
  local digest="$1" url="https://${host}/v2/${path}/manifests/${1}" challenge realm service scope token auth=()
  challenge="$(curl -sS -o /dev/null -D - "$url" | tr -d '\r' | grep -i '^www-authenticate: Bearer ' || true)"
  if [ -n "$challenge" ]; then
    realm="$(sed -n 's/.*realm="\([^"]*\)".*/\1/p' <<<"$challenge")"
    service="$(sed -n 's/.*service="\([^"]*\)".*/\1/p' <<<"$challenge")"
    scope="$(sed -n 's/.*scope="\([^"]*\)".*/\1/p' <<<"$challenge")"
    [ -n "$realm" ] || return 1
    local cred=()
    [ -n "${REGISTRY_TOKEN:-}" ] && cred=(-u "${REGISTRY_USER:-token}:${REGISTRY_TOKEN}")
    token="$(curl -fsS "${cred[@]+"${cred[@]}"}" -G "$realm" --data-urlencode "service=${service}" \
      --data-urlencode "scope=${scope:-repository:${path}:pull}" | sed -n 's/.*"token" *: *"\([^"]*\)".*/\1/p')" || return 1
    [ -n "$token" ] || return 1
    auth=(-H "Authorization: Bearer ${token}")
  fi
  curl -fsS "${auth[@]+"${auth[@]}"}" \
    -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
    -o "$work/manifest" "$url" 2>/dev/null || return 1
  [ "sha256:$(sha256_of "$work/manifest")" = "$digest" ]
}

if helm push "$tgz" "$repo" >"$work/first" 2>&1; then
  cat "$work/first"
  exit 0
fi
cat "$work/first" >&2

orphan="$(grep -oE "$RACE" "$work/first" | head -n1 | grep -oE 'sha256:[0-9a-f]{64}' || true)"
[ -n "$orphan" ] || die "helm push ${tgz} failed, and not with GHCR's tag read-after-write race; not retrying"

echo "::warning::helm push ${name}: the registry accepted manifest ${orphan} but 404'd reading it back to tag it (GHCR read-after-write race). Waiting for it to be served, then tagging that digest."
served=""
for i in $(seq 1 "$attempts"); do
  if fetchable "$orphan"; then served=$i; break; fi
  echo "poll ${i}/${attempts}: ${host}/${path}@${orphan} not served yet"
  [ "$i" -lt "$attempts" ] && sleep "$interval"
done
[ -n "$served" ] \
  || die "${host}/${path}@${orphan} was still not served after ${attempts} polls ${interval}s apart; it is untagged in the registry. Not tagging blind."
echo "${host}/${path}@${orphan} served on poll ${served}; pushing the same archive again to tag that digest"

helm push "$tgz" "$repo" >"$work/second" 2>&1 || { cat "$work/second" >&2; die "the second push of ${tgz} failed too"; }
cat "$work/second"
again="$(sed -n 's/^Digest: \(sha256:[0-9a-f]\{64\}\)$/\1/p' "$work/second" | head -n1)"
[ "$again" = "$orphan" ] \
  || die "the second push of ${tgz} reported digest '${again}', not ${orphan}: the archive changed between pushes, so the tag is not on the manifest first pushed"

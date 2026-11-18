#!/usr/bin/env bash
# Attach files to the GitHub release for a tag, creating the release if nobody has yet.
#
# Usage: [RELEASE_NOTES="..."] publish-release-assets.sh <tag> <file>...
# RELEASE_NOTES is the body used only if this script is the one that creates the release.
#
# WHY THIS IS NOT `gh release view || gh release create`. A tag push starts TWO workflows that both
# want the release: release-tag (this one, to attach the stamped CompositionDefinition) and
# release-notes (the org reusable, which creates the release to write its body). With view-then-create,
# release-tag can see "no release" and then lose the create to release-notes a moment later, and the
# step dies on `HTTP 422 ... Release.tag_name already exists` -- with the chart already pushed and only
# the CompositionDefinition asset missing. That is how glance-kog 0.1.2 failed; keystone-kog 0.4.2 won
# the same race by luck.
#
# So the create is tried and an "already exists" answer is treated as success: someone else created
# the release, which is all this step needed. ANY OTHER create failure (a 403, a 5xx, a typo'd tag)
# still fails the step, and so does a failed upload. Never `|| true` on the whole thing.
set -euo pipefail
tag="${1:?usage: publish-release-assets.sh <tag> <file>...}"; shift
[ "$#" -gt 0 ] || { echo "publish-release-assets: no files to attach" >&2; exit 2; }
notes="${RELEASE_NOTES:-Apply the attached CompositionDefinition to register this version.}"

if gh release view "$tag" >/dev/null 2>&1; then
  echo "release $tag exists"
elif out="$(gh release create "$tag" --title "$tag" --notes "$notes" 2>&1)"; then
  echo "created release $tag"
elif printf '%s' "$out" | grep -qi 'already exists'; then
  echo "release $tag was created concurrently (release-notes runs on the same tag push); attaching to it"
else
  printf '%s\n' "$out" >&2
  echo "publish-release-assets: creating release $tag failed (not a concurrent create)" >&2
  exit 1
fi
gh release upload "$tag" "$@" --clobber
echo "attached to $tag: $*"

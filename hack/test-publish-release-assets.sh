#!/usr/bin/env bash
# Exercise hack/publish-release-assets.sh against a stand-in `gh` (no network, no GitHub token).
# Each case scripts what `release view` and `release create` answer and asserts the exit code and
# whether `release upload` was reached. The race case is the one that broke glance-kog 0.1.2.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/publish-release-assets.sh"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin"; echo "cd" > "$work/cd.yaml"
cat > "$work/bin/gh" <<'GH'
#!/usr/bin/env bash
# Stand-in gh: behaviour from env, every call logged.
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "release view")   [ "$VIEW" = present ] && exit 0 || { echo "release not found" >&2; exit 1; } ;;
  "release create")
    case "$CREATE" in
      ok)     exit 0 ;;
      exists) echo 'HTTP 422: Validation Failed (https://api.github.com/repos/o/r/releases)' >&2
              echo 'Release.tag_name already exists' >&2; exit 1 ;;
      403)    echo 'HTTP 403: Resource not accessible by integration (https://api.github.com/repos/o/r/releases)' >&2; exit 1 ;;
    esac ;;
  "release upload") [ "${UPLOAD:-ok}" = ok ] && exit 0 || { echo "HTTP 500: upload failed" >&2; exit 1; } ;;
esac
echo "unexpected gh call: $*" >&2; exit 99
GH
chmod +x "$work/bin/gh"

fail=0
run() {  # label VIEW CREATE UPLOAD want_exit want_upload(yes|no)
  local label="$1"; export VIEW="$2" CREATE="$3" UPLOAD="$4" GH_LOG="$work/log"; : > "$GH_LOG"
  PATH="$work/bin:$PATH" bash "$script" 1.2.3 "$work/cd.yaml" >"$work/out" 2>&1; local rc=$?
  local uploaded=no; grep -q '^release upload' "$GH_LOG" && uploaded=yes
  local exit_ok=no
  if [ "$5" = 0 ]; then [ "$rc" = 0 ] && exit_ok=yes; else [ "$rc" != 0 ] && exit_ok=yes; fi
  if [ "$exit_ok" = yes ] && [ "$uploaded" = "$6" ]; then
    echo "ok    $label (exit $rc, upload=$uploaded)"
  else
    echo "FAIL  $label: exit $rc (want $5), upload=$uploaded (want $6)"; sed 's/^/      /' "$work/out"; fail=1
  fi
}
run "release already there"                                  present ok     ok   0  yes
run "nobody created it yet"                                  absent  ok     ok   0  yes
run "RACE: view absent, create says already exists"          absent  exists ok   0  yes
run "real create failure (403) still fails, no upload"       absent  403    ok   1  no
run "upload failure still fails"                             present ok     fail 1  yes
# RELEASE_NOTES reaches the create call when set.
export VIEW=absent CREATE=ok UPLOAD=ok GH_LOG="$work/log"; : > "$GH_LOG"
RELEASE_NOTES="custom notes 1.2.3" PATH="$work/bin:$PATH" bash "$script" 1.2.3 "$work/cd.yaml" >/dev/null 2>&1
if grep -q -- '--notes custom notes 1.2.3' "$GH_LOG"; then echo "ok    RELEASE_NOTES is passed to the create"
else echo "FAIL  RELEASE_NOTES was not passed to the create"; sed 's/^/      /' "$GH_LOG"; fail=1; fi
# Self-check: the OLD step (view || create; upload under set -e) must fail the race case, or this
# test could not tell the fix from the bug.
cat > "$work/old.sh" <<'OLD'
set -euo pipefail
gh release view "$1" >/dev/null 2>&1 || gh release create "$1" --title "$1" --notes x
gh release upload "$1" "$2" --clobber
OLD
export VIEW=absent CREATE=exists UPLOAD=ok GH_LOG="$work/log"; : > "$GH_LOG"
if PATH="$work/bin:$PATH" bash "$work/old.sh" 1.2.3 "$work/cd.yaml" >/dev/null 2>&1; then
  echo "FAIL  self-check: the old view||create step passed the race case, so this test detects nothing"; fail=1
else
  echo "ok    self-check: the old view||create step fails the race case"
fi
exit $fail

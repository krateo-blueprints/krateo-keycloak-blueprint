#!/usr/bin/env python3
"""hack/push-chart.sh retries GHCR's tag read-after-write race and nothing else, and every workflow pushes through it.

    hack/validate-push-chart.py [repo-root]

push-chart.sh runs here against a stand-in `helm` (each call follows a script: succeed with a digest, fail with the
race on a digest, or fail with another error) and a stand-in `curl` (a registry with a Bearer token challenge whose
manifest GET 404s until a chosen poll, and requires the token it issued). Cases:

  ok         the first push succeeds                    -> 0, one push, no poll
  race       the race, the digest served on poll 2      -> 0, two pushes, the second on the same digest
  other      the tag step denied on that digest          -> 1, one push, no poll (a near miss of the race string)
  push500    the manifest PUT "not found" on that digest -> 1, one push, no poll (another near miss)
  never      the race, the digest never served          -> 1, one push, "still not served", every poll spent
  moved      the race, the second push on another digest -> 1
  wrongbody  the race, the registry serves other bytes  -> 1 (a body is not the digest until it hashes to it)

Then it mutates copies of push-chart.sh (retry keyed on any error, no poll, no digest comparison, no body hash) and
fails if a case does not notice. Last, every `helm push` in .github/workflows goes through hack/push-chart.sh.

Fails (exit 2) when bash, tar or push-chart.sh is missing, or when no workflow calls push-chart.sh.
"""
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SCRIPT = os.path.join(ROOT, "hack", "push-chart.sh")
WF = os.path.join(ROOT, ".github", "workflows")


def measurement_failed(msg):
    print("FAILED MEASUREMENT: " + msg)
    sys.exit(2)


if not os.path.isfile(SCRIPT):
    measurement_failed("hack/push-chart.sh is missing")
for tool in ("bash", "tar"):
    if shutil.which(tool) is None:
        measurement_failed("%s not on PATH" % tool)

BODY = b'{"schemaVersion":2,"stand-in":"manifest"}'
DIGEST = "sha256:" + hashlib.sha256(BODY).hexdigest()
OTHER = "sha256:" + "0" * 64
RACE = 'Error: failed to perform "Tag" on destination: %s: not found'

HELM = r'''#!/usr/bin/env bash
# stand-in helm: `helm push` follows $STUB/plan, one line per call
[ "$1" = push ] || { echo "stand-in helm: unexpected $*" >&2; exit 99; }
n=$(( $(cat "$STUB/helm.calls" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STUB/helm.calls"
line="$(sed -n "${n}p" "$STUB/plan")"
case "$line" in
  ok\ *) echo "Pushed: x"; echo "Digest: ${line#ok }" ;;
  race\ *) echo "Error: failed to perform \"Tag\" on destination: ${line#race }: not found" >&2; exit 1 ;;
  err\ *) echo "Error: ${line#err }" >&2; exit 1 ;;
  *) echo "stand-in helm: no plan for call $n" >&2; exit 98 ;;
esac
'''

CURL = r'''#!/usr/bin/env bash
# stand-in curl: a registry with a Bearer challenge; the manifest is served from poll $STUB/at on
out="" headers=0 url="" auth=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift ;;
    -D) headers=1; shift ;;
    -H) case "$2" in "Authorization: Bearer "*) auth="${2#Authorization: Bearer }" ;; esac; shift ;;
    -u|--data-urlencode) shift ;;
    -*) ;;
    *) url="$1" ;;
  esac
  shift
done
case "$url" in
  https://auth.stand.in/token*) echo '{"token":"issued-token"}'; exit 0 ;;
  https://reg.stand.in/v2/*/manifests/*) ;;
  *) echo "stand-in curl: unexpected url $url" >&2; exit 99 ;;
esac
if [ "$headers" = 1 ]; then
  printf 'HTTP/2 401\r\nwww-authenticate: Bearer realm="https://auth.stand.in/token",service="reg.stand.in",scope="repository:org/charts/demo:pull"\r\n\r\n'
  exit 0
fi
[ "$auth" = issued-token ] || exit 22
n=$(( $(cat "$STUB/get.calls" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STUB/get.calls"
[ "$n" -ge "$(cat "$STUB/at")" ] || exit 22
cat "$STUB/body" > "$out"
'''

CASES = {
    "ok": (["ok " + DIGEST], 1, BODY),
    "race": (["race " + DIGEST, "ok " + DIGEST], 2, BODY),
    # Near misses, on the same digest, with the digest servable at once: a script keyed on less than the whole race
    # string retries them and succeeds.
    "other": (["err " + (RACE % DIGEST)[len("Error: "):].replace(": not found", ": denied"), "ok " + DIGEST], 1, BODY),
    "push500": (["err failed to perform \"Push\" on destination: %s: not found" % DIGEST, "ok " + DIGEST], 1, BODY),
    "never": (["race " + DIGEST, "ok " + DIGEST], 999, BODY),
    "moved": (["race " + DIGEST, "ok " + OTHER], 1, BODY),
    "wrongbody": (["race " + DIGEST, "ok " + DIGEST], 1, b"other bytes"),
}


def run_case(script, case, tmp):
    plan, at, body = CASES[case]
    stub = tempfile.mkdtemp(dir=tmp)
    bindir = os.path.join(stub, "bin")
    os.makedirs(bindir)
    for name, src in (("helm", HELM), ("curl", CURL)):
        p = os.path.join(bindir, name)
        open(p, "w").write(src)
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    open(os.path.join(stub, "plan"), "w").write("\n".join(plan) + "\n")
    open(os.path.join(stub, "at"), "w").write(str(at))
    open(os.path.join(stub, "body"), "wb").write(body)
    tgz = os.path.join(stub, "demo-0.1.0.tgz")
    with tarfile.open(tgz, "w:gz") as t:
        data = b"name: demo\nversion: 0.1.0\n"
        info = tarfile.TarInfo("demo/Chart.yaml")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    env = dict(os.environ, STUB=stub, PATH=bindir + os.pathsep + os.environ["PATH"], PUSH_POLL_ATTEMPTS="4",
               PUSH_POLL_INTERVAL="0")
    env.pop("REGISTRY_TOKEN", None)
    r = subprocess.run(["bash", script, tgz, "oci://reg.stand.in/org/charts"], env=env, capture_output=True, text=True)

    def count(f):
        p = os.path.join(stub, f)
        return int(open(p).read()) if os.path.exists(p) else 0

    return r.returncode, count("helm.calls"), count("get.calls"), r.stdout + r.stderr


def case_failures(script, tmp):
    out = []
    for case in CASES:
        rc, pushes, gets, log = run_case(script, case, tmp)
        want = {
            "ok": rc == 0 and pushes == 1 and gets == 0,
            "race": rc == 0 and pushes == 2 and gets == 2 and ("Digest: " + DIGEST) in log,
            "other": rc == 1 and pushes == 1 and gets == 0 and "not retrying" in log,
            "push500": rc == 1 and pushes == 1 and gets == 0 and "not retrying" in log,
            "never": rc == 1 and pushes == 1 and gets == 4 and "still not served" in log,
            "moved": rc == 1 and pushes == 2 and "not " + DIGEST in log,
            "wrongbody": rc == 1 and pushes == 1 and "still not served" in log,
        }[case]
        if not want:
            out.append("case %s: rc %d, %d push(es), %d manifest GET(s); log tail: %s"
                       % (case, rc, pushes, gets, " | ".join(log.strip().splitlines()[-3:])))
    return out


failures = []
src = open(SCRIPT).read()
MUTANTS = [
    ("retry keyed on any error (the race string dropped)", "RACE='failed to perform \"Tag\" on destination: sha256:[0-9a-f]{64}: not found'",
     "RACE='sha256:[0-9a-f]{64}'"),
    ("the ': not found' suffix dropped", ': sha256:[0-9a-f]{64}: not found\'', ': sha256:[0-9a-f]{64}\''),
    ("the Tag operation dropped", "RACE='failed to perform \"Tag\" on", "RACE='failed to perform \"[A-Za-z]*\" on"),
    ("no poll", '  if fetchable "$orphan"; then served=$i; break; fi', "  served=$i; break"),
    ("no digest comparison", '[ "$again" = "$orphan" ] \\\n  || die', 'true \\\n  || die'),
    ("no body hash", '[ "sha256:$(sha256_of "$work/manifest")" = "$digest" ]', "true"),
]
with tempfile.TemporaryDirectory() as tmp:
    for f in case_failures(SCRIPT, tmp):
        failures.append("hack/push-chart.sh " + f)
    killed = 0
    for label, a, b in MUTANTS:
        if src.count(a) != 1:
            failures.append("cannot plant mutant '%s': its anchor occurs %d times" % (label, src.count(a)))
            continue
        p = os.path.join(tmp, "mutant.sh")
        open(p, "w").write(src.replace(a, b))
        if case_failures(p, tmp):
            killed += 1
        else:
            failures.append("no case notices push-chart.sh with %s" % label)

calls = 0
for fn in sorted(os.listdir(WF)):
    if not fn.endswith((".yaml", ".yml")):
        continue
    for n, line in enumerate(open(os.path.join(WF, fn)), 1):
        code = line.split("#", 1)[0] if line.lstrip().startswith("#") else line
        if re.search(r"(^|[\s;&|(])helm push\b", code) and not line.lstrip().startswith("#"):
            failures.append("%s:%d runs `helm push` directly; push through hack/push-chart.sh, which survives the GHCR "
                            "tag race" % (fn, n))
        if "hack/push-chart.sh" in code and not line.lstrip().startswith("#"):
            calls += 1
if calls == 0:
    measurement_failed("no workflow calls hack/push-chart.sh, so nothing pushes through it")

if failures:
    for f in failures:
        print("FAIL: " + f)
    sys.exit(1)
print("OK: hack/push-chart.sh passes %d stand-in cases (the race retried on the same digest after the digest is served; "
      "another error, a never-served digest, a moved digest and a wrong body fail); %d mutant(s) killed; %d workflow "
      "call(s), no bare helm push" % (len(CASES), killed, calls))

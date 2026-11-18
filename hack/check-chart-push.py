#!/usr/bin/env python3
"""Every chart push goes through the organisation's chart-push action, pinned by commit.

    hack/check-chart-push.py [repo-root]

The push itself, and its tests (GHCR's tag read-after-write race retried on the same digest and nothing else), live
in krateo-platformops/.github/.github/actions/chart-push. This repository keeps no copy of it. What is checked here is
the part only this repository can get wrong:

  - no workflow runs `helm push` itself (a bare push has no race handling and no digest check);
  - every use of the chart-push action is pinned to a 40-hex commit (a branch or tag ref can move under a release);
  - at least one workflow uses it (otherwise nothing pushes through it, and the first two checks pass vacuously);
  - nothing still calls the retired hack/push-chart.sh.

Then the checks are run against mutated copies of the workflows (a bare `helm push` added, the pin moved to @main,
the action removed) and must fail on each, so a check that matches nothing cannot pass.
Exit 1 on a finding, 2 when the workflows cannot be read.
"""
import glob
import os
import re
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
ACTION = "krateo-platformops/.github/.github/actions/chart-push"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*" + re.escape(ACTION) + r"@(\S+)")
PINNED = re.compile(r"^[0-9a-f]{40}$")
BARE_PUSH = re.compile(r"(^|[\s;&|(])helm\s+push(\s|$)")


def code(line):
    s = line.lstrip()
    return "" if s.startswith("#") else line


def findings(files):
    out, uses = [], 0
    for path, text in files.items():
        for n, line in enumerate(text.splitlines(), 1):
            c = code(line)
            if not c:
                continue
            if BARE_PUSH.search(c):
                out.append("%s:%d runs `helm push` itself; push through %s" % (path, n, ACTION))
            if "hack/push-chart.sh" in c:
                out.append("%s:%d calls the retired hack/push-chart.sh; use %s" % (path, n, ACTION))
            m = USES.match(c)
            if m:
                uses += 1
                if not PINNED.match(m.group(1)):
                    out.append("%s:%d pins %s to '%s', not a 40-hex commit" % (path, n, ACTION, m.group(1)))
    if uses == 0:
        out.append("no workflow uses %s, so nothing pushes through it" % ACTION)
    return out


paths = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.y*ml")))
if not paths:
    print("MEASUREMENT FAILED: no workflows under %s/.github/workflows" % ROOT)
    sys.exit(2)
files = {os.path.relpath(p, ROOT): open(p).read() for p in paths}

failures = findings(files)

# Mutants: each must produce a finding, or the check proves nothing.
user = next((p for p, t in files.items() if any(USES.match(code(l)) for l in t.splitlines())), None)
if user:
    mutants = {
        "a bare `helm push` step": dict(files, **{user: files[user] + "\n      - run: helm push x.tgz oci://ghcr.io/x\n"}),
        "the pin moved to @main": dict(files, **{user: re.sub(re.escape(ACTION) + r"@[0-9a-f]{40}", ACTION + "@main", files[user])}),
        "the action removed": dict(files, **{user: "\n".join(l for l in files[user].splitlines() if not USES.match(code(l)))}),
        "push-chart.sh called again": dict(files, **{user: files[user] + "\n      - run: bash hack/push-chart.sh x.tgz oci://ghcr.io/x\n"}),
    }
    for label, mutant in mutants.items():
        if not findings(mutant):
            failures.append("the check does not notice %s" % label)

if failures:
    for f in failures:
        print("FAIL: " + f)
    sys.exit(1)
print("OK: %d workflow(s); every chart push goes through %s pinned by commit; 4 mutants noticed" % (len(files), ACTION))

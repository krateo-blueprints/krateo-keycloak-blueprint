#!/usr/bin/env python3
"""CI gate: keycloak-operator renders the two upstream Keycloak CRDs from templates/, unchanged
except for `helm.sh/resource-policy: keep`.

WHY. A chart's crds/ directory is installed once and never upgraded by Helm, so an operator bump that
changes a CRD would silently not reach a cluster that already had it. 0.3.0 renders the CRDs as
templates instead, through fromYaml/toYaml. That round trip, or a later template edit, could alter a
CRD; and without `keep`, `helm uninstall` would delete the CRDs and with them every Keycloak in the
cluster.

WHAT. (1) No chart ships a crds/ directory. (2) The rendered CRDs are exactly the files under
files/crds/, parsed, plus the keep annotation: nothing added, removed or changed. (3) Those files'
sha256 match VENDOR.md's upstream column (prefix), so they stay byte-identical to upstream.
SELF-TEST: a copy of the chart whose template drops the annotation must fail check (2).
"""
import copy, hashlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import yaml

CHART = Path("helm/keycloak-operator")


def render(chart):
    work = Path(tempfile.mkdtemp(prefix="crds-"))
    try:
        dst = work / "c"
        shutil.copytree(chart, dst)
        cy = dst / "Chart.yaml"
        cy.write_text(cy.read_text().replace("CHART_VERSION", "0.0.0-ci"))
        mutate(dst)
        p = subprocess.run(["helm", "template", "r", str(dst), "-n", "kcop", "--set", "watchNamespaces=kcop"], capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(f"::error::render failed: {p.stderr.strip()[:400]}")
        return {d["metadata"]["name"]: d for d in yaml.safe_load_all(p.stdout) if d and d["kind"] == "CustomResourceDefinition"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


mutate = lambda dst: None


def problems(rendered):
    errs = []
    vendored = {}
    for f in sorted((CHART / "files" / "crds").glob("*.yml")):
        d = yaml.safe_load(f.read_text())
        vendored[d["metadata"]["name"]] = d
    if set(rendered) != set(vendored):
        errs.append(f"rendered CRDs {sorted(rendered)} != vendored {sorted(vendored)}")
    for name, v in vendored.items():
        r = rendered.get(name)
        if r is None:
            continue
        want = copy.deepcopy(v)
        want["metadata"].setdefault("annotations", {})["helm.sh/resource-policy"] = "keep"
        if r != want:
            errs.append(f"{name}: rendered CRD differs from files/crds plus the keep annotation")
    return errs


errors = []
for cy in Path("helm").glob("*/Chart.yaml"):
    if (cy.parent / "crds").exists():
        errors.append(f"{cy.parent}/crds exists: Helm never upgrades crds/; render CRDs from templates/")
vendor = (CHART / "VENDOR.md").read_text()
for f in sorted((CHART / "files" / "crds").glob("*.yml")):
    m = re.search(r"`files/crds/" + re.escape(f.name) + r"`[^\n]*`([0-9a-f]{8,})", vendor)
    got = hashlib.sha256(f.read_bytes()).hexdigest()
    if not m or not got.startswith(m.group(1).rstrip("…")):
        errors.append(f"{f}: sha256 {got[:16]} does not match VENDOR.md")

def drop_keep(dst):
    t = dst / "templates" / "crds.yaml"
    t.write_text(t.read_text().replace('"helm.sh/resource-policy" "keep"', '"x-test" "mutant"'))
mutate = drop_keep
if not problems(render(CHART)):
    sys.exit("::error::self-test: a template without the keep annotation passed; the gate is broken")
mutate = lambda dst: None
errors += problems(render(CHART))
for e in errors:
    print(f"::error::{e}")
if errors:
    sys.exit(1)
print("Checked: no crds/ directory; rendered CRDs == files/crds + keep; files match VENDOR.md's upstream sha256.")

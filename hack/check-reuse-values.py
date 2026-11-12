#!/usr/bin/env python3
"""CI gate: every chart renders with the values of its previous releases, as `helm upgrade
--reuse-values` gives them.

WHY. With --reuse-values Helm upgrades using the PREVIOUS release's values and does not apply the new
chart's values.yaml defaults. A template that reads a key added since then (e.g. 0.2.6's
`.Values.crdOwnershipBridge.enabled`) fails with a nil pointer, and the upgrade aborts.

WHAT. For each chart and each previous semver tag listed below, render the chart with its values.yaml
REPLACED by that tag's values.yaml (exactly the reuse-values shape), and require success. The render
with the chart's own defaults must produce the same kinds, so a defaulted key cannot silently switch a
feature off under reuse-values either.
SELF-TEST: a template reading a key absent from the old values must fail the render.
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path
import yaml

CHARTS = {"helm/keycloak-operator": ["0.2.4", "0.2.5"]}
SETS = {"helm/keycloak-operator": ["--set", "watchNamespaces=kcop"]}


def render(chart, values_text, extra_template=None):
    work = Path(tempfile.mkdtemp(prefix="reuse-"))
    try:
        dst = work / "c"
        shutil.copytree(chart, dst)
        cy = dst / "Chart.yaml"
        cy.write_text(cy.read_text().replace("CHART_VERSION", "0.0.0-ci"))
        if values_text is not None:
            (dst / "values.yaml").write_text(values_text)
        if extra_template:
            (dst / "templates" / "zz-selftest.yaml").write_text(extra_template)
        p = subprocess.run(["helm", "template", "r", str(dst), "-n", "kcop", *SETS.get(chart, [])], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def kinds(out):
    return sorted((d["kind"], d["metadata"]["name"]) for d in yaml.safe_load_all(out) if d)


errors = []
for chart, tags in CHARTS.items():
    rc, ref, err = render(chart, None)
    if rc != 0:
        errors.append(f"{chart}: does not render with its own defaults: {err.strip()[:300]}")
        continue
    for tag in tags:
        old = subprocess.run(["git", "show", f"{tag}:{chart}/values.yaml"], capture_output=True, text=True)
        if old.returncode != 0:
            errors.append(f"{chart}: cannot read values.yaml at tag {tag}: {old.stderr.strip()[:200]}")
            continue
        sel = render(chart, old.stdout, "{{ if .Values.selfTestKeyAddedLater.enabled }}x{{ end }}\n")
        if sel[0] == 0:
            sys.exit("::error::self-test: a template reading an absent key rendered; the gate is broken")
        rc, out, err = render(chart, old.stdout)
        if rc != 0:
            errors.append(f"{chart}: `helm upgrade --reuse-values` from {tag} would fail: {err.strip()[:300]}")
        elif kinds(out) != kinds(ref):
            errors.append(f"{chart}: under {tag}'s values it renders {kinds(out)} instead of {kinds(ref)}")
for e in errors:
    print(f"::error::{e}")
if errors:
    sys.exit(1)
print("Checked: each chart renders, with the same objects, under its previous releases' values (--reuse-values).")

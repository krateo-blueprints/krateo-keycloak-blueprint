#!/usr/bin/env python3
"""CI gate for keycloak.bootstrapAdminPassword: the decision that REUSES the bootstrap admin password
already in the cluster, takes an explicit one, or generates a new one.

Pattern and reasoning from krateo-platformops/installer#782 (check-signing-key.py).

WHY THE REUSE ARM IS THE ONE THAT MATTERS. The Keycloak operator applies spec.bootstrapAdmin only on
the server's FIRST start; afterwards the password lives in Keycloak's database. If the reuse arm stops
firing, every upgrade generates a new password, helm applies it without complaint, and the Secret
silently stops matching the live admin. Nothing errors, and the next person who reads the Secret is
locked out with nothing saying why.

WHY IT NEEDS A GATE. `helm template` disables `lookup`, so a decision sitting next to its own lookup
can only ever render its generate arm. The helper therefore takes the looked-up Secret as an
argument, which lets this gate hand it a found Secret and nothing at all.

WHAT IT ASSERTS:
  1. explicit password                       -> returned as given, even when a Secret exists
  2. found Secret with data.password         -> returns THAT password, byte for byte
  3. no Secret / no data / empty data / wrong key -> generates 32 alphanumerics
  4. two generate calls differ               -> generation is live (not a constant)
  5. the reuse result differs from a generated one
  6. a MUTANT with the reuse branch deleted FAILS assertion 2 -> this gate can detect the regression
  7. secrets.yaml (textually): ONE variable names the lookup and metadata.name, and the looked-up
     object is what is passed to the helper

WHAT IT CANNOT DO: execute `lookup`. It proves that IF the lookup finds the Secret, the password is
reused, and that the lookup is wired with the same name as the Secret it emits. It cannot prove the
lookup finds it on a live cluster (namespace at runtime, RBAC).

Usage: hack/check-bootstrap-password.py   (run from the repo root; needs helm and pyyaml)
"""
import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HELPERS = Path("helm/keycloak/templates/_helpers.tpl")
SECRETS = Path("helm/keycloak/templates/secrets.yaml")
HELPER = "keycloak.bootstrapAdminPassword"

SENTINEL = "SENTINEL-EXISTING-PASSWORD-MUST-NOT-CHANGE"
SENTINEL_B64 = base64.b64encode(SENTINEL.encode()).decode()

# (label, looked-up Secret, explicit value, expectation)
CASES = [
    ("explicit password wins over an existing Secret", {"data": {"password": SENTINEL_B64}}, "chosen", "explicit"),
    ("Secret present with password -> REUSE IT", {"data": {"password": SENTINEL_B64}}, "", "reuse"),
    ("no Secret at all -> generate", None, "", "generate"),
    ("Secret present, data empty -> generate", {"data": {}}, "", "generate"),
    ("Secret present, no data field -> generate", {"metadata": {"name": "x"}}, "", "generate"),
    ("Secret present, different key -> generate", {"data": {"other": SENTINEL_B64}}, "", "generate"),
    ("no Secret, second call -> generate (must differ from the first)", None, "", "generate"),
]

PROBE = (
    "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: probe\ndata:\n"
    "{{- range $i, $c := .Values.cases }}\n"
    '  case{{ $i }}: {{ (include "' + HELPER + '" (list $c.found $c.explicit)) | b64enc | quote }}\n'
    "{{- end }}\n"
)


def render(helpers_text):
    work = Path(tempfile.mkdtemp(prefix="bootstrap-pw-"))
    try:
        chart = work / "probe"
        (chart / "templates").mkdir(parents=True)
        (chart / "Chart.yaml").write_text("apiVersion: v2\nname: probe\nversion: 0.0.0\n")
        (chart / "templates" / "_helpers.tpl").write_text(helpers_text)
        (chart / "templates" / "probe.yaml").write_text(PROBE)
        (chart / "values.yaml").write_text("cases: []\n")
        vals = work / "cases.yaml"
        vals.write_text(yaml.safe_dump({"cases": [{"found": f, "explicit": e} for _, f, e, _ in CASES]}))
        p = subprocess.run(["helm", "template", "probe", str(chart), "-f", str(vals)], capture_output=True, text=True)
        if p.returncode != 0:
            return {"__error__": p.stderr.strip()[:1200]}
        doc = next(d for d in yaml.safe_load_all(p.stdout) if isinstance(d, dict) and d.get("kind") == "ConfigMap")
        return {k: base64.b64decode(v).decode() for k, v in (doc.get("data") or {}).items()}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def judge(out):
    """Return the list of failed assertions for one render."""
    if "__error__" in out:
        return [f"render failed: {out['__error__']}"]
    errors, generated = [], []
    for i, (label, _found, explicit, want) in enumerate(CASES):
        got = out.get(f"case{i}")
        if want == "explicit" and got != explicit:
            errors.append(f"{label}: expected the explicit value, got {got!r}")
        elif want == "reuse" and got != SENTINEL:
            errors.append(f"{label}: expected the EXISTING password, got a different value (it would rotate)")
        elif want == "generate":
            if not (got and len(got) == 32 and got.isalnum()) or got == SENTINEL:
                errors.append(f"{label}: expected 32 generated alphanumerics, got {got!r}")
            generated.append(got)
    if len(set(generated)) != len(generated):
        errors.append("two generate calls returned the same value: generation is not live")
    if out.get("case1") in generated:
        errors.append("the reuse arm returned a generated value")
    return errors


def wiring():
    s = SECRETS.read_text()
    errors = []
    m = re.search(r'\$(\w+)\s*:=\s*lookup\s+"v1"\s+"Secret"\s+\.Release\.Namespace\s+\$(\w+)', s)
    if not m:
        return ['secrets.yaml no longer performs `lookup "v1" "Secret" .Release.Namespace $<name>`']
    found_var, name_var = m.group(1), m.group(2)
    if not re.search(r"name:\s*\{\{\s*\$" + name_var + r"\s*\}\}", s):
        errors.append(f"metadata.name is not the same variable ${name_var} the lookup uses")
    if not re.search(r'include\s+"' + re.escape(HELPER) + r'"\s+\(list\s+\$' + found_var + r"\b", s):
        errors.append(f"the looked-up ${found_var} is not what is passed to {HELPER}")
    pw = re.search(r"\$(\w+)\s*:=\s*include\s+\"" + re.escape(HELPER) + '"', s)
    if not pw or not re.search(r"password:\s*\{\{\s*\$" + pw.group(1) + r"\b", s):
        errors.append("the emitted password is not the helper's result")
    return errors


def main():
    helpers = HELPERS.read_text()
    errors = judge(render(helpers))
    # Mutant: delete the reuse branch. The gate must catch it, or its silence means nothing.
    mutant = re.sub(r'\{\{- else if and \$found \$found\.data \(hasKey \$found\.data "password"\) -\}\}\n'
                    r'\{\{- index \$found\.data "password" \| b64dec -\}\}\n', "", helpers)
    if mutant == helpers:
        errors.append("could not build the mutant: the reuse branch changed shape, update this gate")
    elif not judge(render(mutant)):
        errors.append("the MUTANT with the reuse branch deleted PASSED: this gate cannot detect the regression")
    errors += wiring()
    print(f"Checked {len(CASES)} helper cases, a reuse-deleted mutant, and the secrets.yaml wiring.")
    for e in errors:
        print(f"::error::{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

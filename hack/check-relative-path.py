#!/usr/bin/env python3
"""CI gate for keycloak.http.relativePath (Keycloak's http-relative-path).

Keycloak builds the token issuer from keycloak.hostname and serves under the relative path. If the two
disagree, tokens carry an issuer the gateway does not serve, or the gateway forwards to a path Keycloak
does not serve, and both fail as authentication errors rather than as routing errors. The chart refuses
the mismatch at render; this gate keeps that refusal, and the rendering itself, from regressing.

Asserts, by rendering a stamped copy of helm/keycloak:
  1. default (no relativePath)                       -> no http-relative-path option rendered
  2. relativePath /keycloak + hostname .../keycloak   -> exactly one http-relative-path=/keycloak, other
                                                         additionalOptions kept
  3. hostname without the path                        -> render refused, naming both keys
  4. trailing slash                                   -> render refused
  5. http-relative-path set via additionalOptions     -> render refused, pointing at relativePath
  6. self-test: the case-2 render with the option stripped is detected by the case-2 check
Measured live (disposable GKE, keycloak-operator 0.3.0, Keycloak 26.6.3, 2026-11-13): with
relativePath /keycloak the server answers under /keycloak only (root 404), the issuer is
<hostname>/realms/<realm>, and the operator moves its probes to /keycloak/health/* on 9000.
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path
import yaml

CHART = Path("helm/keycloak")


def render(*args):
    work = Path(tempfile.mkdtemp(prefix="relpath-"))
    try:
        dst = work / "c"
        shutil.copytree(CHART, dst)
        cy = dst / "Chart.yaml"
        cy.write_text(cy.read_text().replace("CHART_VERSION", "0.0.0-ci"))
        p = subprocess.run(["helm", "template", "t", str(dst), *args], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def options(out):
    kc = next(d for d in yaml.safe_load_all(out) if d and d.get("kind") == "Keycloak")
    return kc["spec"].get("additionalOptions") or []


def case2_ok(opts):
    rp = [o for o in opts if o.get("name") == "http-relative-path"]
    return len(rp) == 1 and rp[0].get("value") == "/keycloak" and any(o.get("name") == "metrics-enabled" for o in opts)


errors = []
rc, out, err = render()
if rc != 0 or any(o.get("name") == "http-relative-path" for o in options(out)):
    errors.append(f"default render must not set http-relative-path (rc={rc}): {err.strip()[:200]}")

OK = ["--set", "keycloak.http.relativePath=/keycloak", "--set", "keycloak.hostname=https://portal.example.com/keycloak",
      "--set", "keycloak.additionalOptions[0].name=metrics-enabled", "--set-string", "keycloak.additionalOptions[0].value=true"]
rc, out, err = render(*OK)
opts = options(out) if rc == 0 else []
if not case2_ok(opts):
    errors.append(f"relativePath /keycloak must render exactly one http-relative-path=/keycloak and keep other options (rc={rc}): {opts} {err.strip()[:200]}")
if case2_ok([o for o in opts if o.get("name") != "http-relative-path"]):
    errors.append("self-test: stripping http-relative-path was NOT detected")

for desc, args, needle in (
        ("hostname without the path", ["--set", "keycloak.http.relativePath=/keycloak", "--set", "keycloak.hostname=https://portal.example.com"],
         "must end with keycloak.http.relativePath"),
        ("trailing slash", ["--set", "keycloak.http.relativePath=/keycloak/", "--set", "keycloak.hostname=https://portal.example.com/keycloak"],
         "relativePath"),
        ("http-relative-path via additionalOptions", ["--set", "keycloak.additionalOptions[0].name=http-relative-path",
                                                       "--set", "keycloak.additionalOptions[0].value=/x"],
         "set the path prefix with keycloak.http.relativePath")):
    rc, out, err = render(*args)
    if rc == 0 or needle not in err:
        errors.append(f"{desc}: render must be refused mentioning {needle!r} (rc={rc}): {err.strip()[:200]}")

for e in errors:
    print(f"::error::{e}")
if errors:
    sys.exit(1)
print("Checked keycloak.http.relativePath: rendered as one http-relative-path, mismatched hostname / trailing slash / "
      "additionalOptions refused, self-test detects a missing option.")

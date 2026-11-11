#!/usr/bin/env python3
"""CI gate: a chart's values.schema.json must not `required` a key that values.yaml defaults.

WHY. Krateo's core-provider turns a chart's values.schema.json into the CRD of its Composition kind,
and `required` becomes a mandatory field of that CRD. The values.yaml defaults do NOT populate the
Composition CR: they apply at render time, after the apiserver has validated the CR. So a `required`
key that values.yaml already defaults enforces nothing at render, and costs everything at admission:
a CR that omits it (or supplies a partial parent object) is rejected. On a platform umbrella that
rejection happens inside the umbrella's own reconcile and freezes every component it manages.
Measured on demo, 2026-11-11: keycloak 0.2.3's root `required: [keycloak, db]` froze all 108 children.

WHAT IT CHECKS. For every chart in the repo (each Chart.yaml outside vendored charts/): every object
node of the schema reached through `properties` that lists `required`, each required key that has a
value in values.yaml at the same path is an error. `required` inside array `items` is left alone:
list items come entirely from the consumer, so there is no default to conflict with.

SELF-TEST. Before judging the real schemas, the gate runs its detector on a mutant of each one (a
root `required` naming a defaulted key) and on a control (a required key with no default). If the
mutant passes or the control fails, the gate itself is broken and says so.

Usage: hack/check-schema-required.py   (from the repo root; needs pyyaml)
"""
import copy
import json
import sys
from pathlib import Path

import yaml

MISSING = object()


def default_at(values, path):
    node = values
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return MISSING
        node = node[key]
    return node


def violations(schema, values, path=()):
    """Every (dotted key) that the schema requires while values.yaml defaults it."""
    found = []
    if not isinstance(schema, dict):
        return found
    for key in schema.get("required") or []:
        if default_at(values, path + (key,)) is not MISSING:
            found.append(".".join(path + (key,)))
    for key, child in (schema.get("properties") or {}).items():
        found += violations(child, values, path + (key,))
    return found


def self_test(schema, values):
    """The detector must flag a mutant and must not flag a control. Returns error strings."""
    errors = []
    defaulted = [k for k in (schema.get("properties") or {}) if default_at(values, (k,)) is not MISSING]
    if defaulted:
        mutant = copy.deepcopy(schema)
        mutant["required"] = list(mutant.get("required") or []) + [defaulted[0]]
        if defaulted[0] not in violations(mutant, values):
            errors.append(f"self-test: a mutant requiring the defaulted key {defaulted[0]!r} was NOT flagged")
    control = copy.deepcopy(schema)
    absent = "__no_default_here__"
    control.setdefault("properties", {})[absent] = {"type": "string"}
    control["required"] = [absent]
    if absent in violations(control, values):
        errors.append("self-test: a control requiring a key with no default WAS flagged")
    return errors


def main():
    errors, checked = [], 0
    for chart_yaml in sorted(Path(".").rglob("Chart.yaml")):
        if "charts" in chart_yaml.parent.parts[:-1] or ".git" in chart_yaml.parts:
            continue
        chart = chart_yaml.parent
        schema_file, values_file = chart / "values.schema.json", chart / "values.yaml"
        if not schema_file.exists():
            continue
        schema = json.loads(schema_file.read_text())
        values = yaml.safe_load(values_file.read_text()) if values_file.exists() else {}
        checked += 1
        errors += [f"{chart}: {e}" for e in self_test(schema, values or {})]
        for key in violations(schema, values or {}):
            errors.append(
                f"{schema_file}: `{key}` is required but values.yaml defaults it. The Composition CRD "
                f"would make it mandatory and reject any CR that omits it; drop it from `required`."
            )
    print(f"Checked {checked} chart schema(s) for required keys that values.yaml defaults.")
    for e in errors:
        print(f"::error::{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

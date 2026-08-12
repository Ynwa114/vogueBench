"""Schema integrity — the migration safety net."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from decode.pipeline import garment_prompt, load_vocab  # noqa: E402
from decode.predicates import AllOf, AnyOf, Cmp, PRED_PATH, load_predicates  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(f"{name}: {detail}")


def leaves(node) -> list[Cmp]:
    if isinstance(node, Cmp):
        return [node]
    if isinstance(node, (AnyOf, AllOf)):
        return [c for n in node.clauses for c in leaves(n)]
    return []


def main() -> int:
    vocab = load_vocab()
    fields = vocab["fields"]
    raw_pred = yaml.safe_load(PRED_PATH.read_text())
    derived = set(raw_pred.get("derived_fields", {}))
    preds = load_predicates()

    print("vocabulary internal consistency")
    total_w = sum(s.get("weight", 0) for s in fields.values())
    check("weights sum to 1.0", abs(total_w - 1.0) < 1e-6, f"got {total_w}")
    for fname, spec in fields.items():
        legal = set(spec["values"])
        check(f"{fname}: no duplicate values", len(spec["values"]) == len(legal), "duplicate values")
        for grp in spec.get("near", []):
            bad = set(grp) - legal
            check(f"{fname}: near group values legal", not bad, f"unknown {sorted(bad)}")
        if applies := spec.get("applies_to"):
            bad = set(applies) - set(fields["category"]["values"])
            check(f"{fname}: applies_to are real categories", not bad, f"unknown {sorted(bad)}")

    print("\ncategories in a near-group share applies_to membership")
    cat_near = [set(group) for group in fields["category"].get("near", [])]
    for fname, spec in fields.items():
        applies = spec.get("applies_to")
        if not applies:
            continue
        scope = set(applies)
        for group in cat_near:
            inside = group & scope
            if inside and inside != group:
                check(f"{fname}: near-group {sorted(group)} split by applies_to", False,
                      f"in scope: {sorted(inside)}, missing: {sorted(group - inside)}")
            else:
                check(f"{fname}: near-group {sorted(group)} consistent", True)

    print("\npredicate groundings reference live schema")
    for name, predicate in preds.items():
        for node in (predicate.grounding, predicate.penalise):
            if node is None:
                continue
            for clause in leaves(node):
                known = clause.field in fields or clause.field in derived
                check(f"{name}: field '{clause.field}' exists", known,
                      "not in vocab.yaml fields or derived_fields")
                if clause.field in fields and clause.op in ("in", "not in", "==", "!="):
                    legal = set(fields[clause.field]["values"])
                    values = clause.value if isinstance(clause.value, list) else [clause.value]
                    bad = [value for value in values if isinstance(value, str) and value not in legal]
                    check(f"{name}: values legal for '{clause.field}'", not bad, f"illegal {bad}")

    print("\nderived fields are declared, not implied")
    used_derived = {clause.field for predicate in preds.values()
                    for node in (predicate.grounding, predicate.penalise) if node is not None
                    for clause in leaves(node) if clause.field not in fields}
    for name in sorted(used_derived):
        check(f"derived field '{name}' is declared", name in derived, "used but absent from derived_fields")

    print("\ndecode prompt tracks the vocabulary")
    prompt = garment_prompt(vocab, "top", "x", "none")
    template = prompt[prompt.find("Return strict JSON"):]
    template_fields = set(re.findall(r'"(\w+)":\s*\{"value"', template))
    check("prompt template covers every field", template_fields == set(fields),
          f"missing {sorted(set(fields) - template_fields)}, stale {sorted(template_fields - set(fields))}")
    for name in fields:
        check(f"prompt lists values for '{name}'", f"- {name}:" in prompt, "absent from sheet")

    print("\ngolden set entries use live schema")
    entries = sorted((ROOT / "eval" / "golden_set").glob("*.json"))
    check("golden set is non-empty", bool(entries), "no labelled entries found")
    for path in entries:
        entry = json.loads(path.read_text())
        market = entry.get("market")
        check(f"{path.name}: market text when supplied",
              market is None or (isinstance(market, str) and market.strip()), "invalid market")
        ocr = entry.get("ocr")
        if ocr is not None:
            valid_keys = {"brand", "product_title", "price", "source_domain", "evidence"}
            check(f"{path.name}: OCR keys known", isinstance(ocr, dict) and set(ocr) <= valid_keys,
                  f"unknown {sorted(set(ocr) - valid_keys) if isinstance(ocr, dict) else 'non-object'}")
            for name in ("brand", "product_title", "price", "source_domain"):
                check(f"{path.name}: OCR '{name}' text or null",
                      ocr.get(name) is None or isinstance(ocr.get(name), str), "invalid type")
            check(f"{path.name}: OCR evidence strings",
                  isinstance(ocr.get("evidence", []), list) and
                  all(isinstance(item, str) for item in ocr.get("evidence", [])), "invalid type")
        conflicts = entry.get("attribute_conflicts", [])
        valid_conflict_keys = {"field", "pixel_value", "external_value", "external_source", "resolution"}
        check(f"{path.name}: attribute conflicts are auditable",
              isinstance(conflicts, list) and all(
                  isinstance(conflict, dict) and set(conflict) == valid_conflict_keys and
                  conflict.get("resolution") == "pixel_read_wins" for conflict in conflicts),
              "invalid conflict record")
        for index, garment in enumerate(entry.get("garments", [])):
            for name, value in garment.items():
                if name in ("role", "brand", "brand_evidence"):
                    continue
                if name not in fields:
                    check(f"{path.name}[{index}]: field '{name}'", False, "not in vocab.yaml")
                    continue
                values = value if isinstance(value, list) else [value]
                bad = [item for item in values if item not in fields[name]["values"]]
                check(f"{path.name}[{index}]: '{name}' values legal", not bad, f"illegal {bad}")

    print("\nno stale identifiers in active code")
    RETIRED = {"modesty", "coverage", "sleeve"}
    for path in sorted((ROOT / "decode").glob("*.py")):
        for term in RETIRED:
            hits = [line for line in path.read_text().splitlines()
                    if re.search(rf"\b{term}\b", line) and not line.strip().startswith("#")
                    and "RETIRED" not in line]
            check(f"{path.name}: no live '{term}'", not hits,
                  f"{len(hits)} line(s), first: {hits[0].strip()[:60] if hits else ''}")

    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURES'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

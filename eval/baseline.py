"""
Baseline harness — score competitors on TWIN-FASHION-90 with our own rubric.

Why this exists: we have no floor. "Our search is good" is unfalsifiable until
there is a number attached to somebody else's search on the same queries. This
walks you through the query set against a named engine, records per-screen scores,
and prints the comparison table.

  python -m eval.baseline --engine twin_shop --class negation
  python -m eval.baseline --engine google_lens --resume
  python -m eval.baseline --report

Volume is deliberately human: ~57 queries, typed by hand, one screenshot each.
That is research, and it stays research. Do not automate this into a crawler —
past a certain volume it stops being benchmarking and starts being a data
pipeline built on someone else's product, which is both a different legal
question and, more importantly, a worse idea: it would teach us to imitate a
competitor's catalog strategy instead of measuring our own.

SCORING NOTE — the rubric is per-SCREEN, not per-item. Ten correct near-identical
results is a failing screen, because she still cannot choose. This is the whole
reason we are not using P@10 alone.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERIES = ROOT / "eval" / "queries" / "twin-fashion-90.yaml"
RESULTS = ROOT / "eval" / "baselines"

ENGINES = ["twin_shop", "google_lens", "google_search", "myntra_search",
           "meesho_image_search", "twin"]

# Per-screen criteria. Order matters — constraint is checked first and is fatal.
RUBRIC = [
    ("constraint", "Any violation of a stated exclusion? (y = violated)", "binary_fatal"),
    ("would_save", "Would this shopper plausibly save at least one item? (0-2)", "scale"),
    ("contrast", "Real choices, or N of the same thing? (0-2)", "scale"),
    ("completeness", "For variant queries: was the range shown? (0-2, na)", "scale"),
]

SCALE_HELP = """
  0 = no / absent
  1 = partially
  2 = yes, clearly
  s = skip this query
  q = save and quit
"""


def load_queries(only_class: str | None = None) -> list[dict]:
    doc = yaml.safe_load(QUERIES.read_text())
    out = []
    for cname, cbody in doc["classes"].items():
        if only_class and cname != only_class:
            continue
        for q in cbody["queries"]:
            out.append({
                "class": cname,
                "q": q["q"],
                "note": q.get("note"),
                "must_not": q.get("must_not", []),
                "expect_facets": q.get("expect_facets", []),
                "requires": q.get("requires", []),
                "source": q.get("source"),
                "expected_behaviour": cbody.get("expected_behaviour", ""),
            })
    return out


def score_path(engine: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    return RESULTS / f"{engine}.jsonl"


def already_scored(engine: str) -> set[str]:
    p = score_path(engine)
    if not p.exists():
        return set()
    return {json.loads(l)["q"] for l in p.read_text().splitlines() if l.strip()}


def ask(prompt: str) -> str:
    return input(prompt).strip().lower()


def run(engine: str, only_class: str | None, resume: bool) -> None:
    qs = load_queries(only_class)
    done = already_scored(engine) if resume else set()
    todo = [q for q in qs if q["q"] not in done]

    print(f"\nScoring {engine} — {len(todo)} queries "
          f"({len(done)} already done)\n{SCALE_HELP}")

    out = score_path(engine)
    for i, q in enumerate(todo, 1):
        print("\n" + "=" * 72)
        print(f"[{i}/{len(todo)}]  class: {q['class']}")
        print(f"QUERY:  {q['q']}")
        if q["requires"]:
            print(f"        (requires: {', '.join(q['requires'])})")
        if q["must_not"]:
            print(f"MUST NOT CONTAIN: {', '.join(q['must_not'])}")
        if q["expect_facets"]:
            print(f"EXPECTED FACETS:  {', '.join(q['expect_facets'])}")
        if q["note"]:
            print(f"NOTE:   {q['note']}")
        print(f"\nPASS CONDITION: {q['expected_behaviour'].strip()}")
        print("-" * 72)
        print("Run the query, screenshot the result screen, then score it.\n")

        rec: dict = {"engine": engine, "class": q["class"], "q": q["q"],
                     "scored_at": str(date.today())}
        quit_now = False

        for key, prompt, kind in RUBRIC:
            if key == "completeness" and q["class"] != "completeness":
                rec[key] = None
                continue
            if key == "constraint" and not q["must_not"]:
                rec[key] = None
                continue
            while True:
                a = ask(f"  {prompt} > ")
                if a == "q":
                    quit_now = True
                    break
                if a == "s":
                    rec = {}
                    break
                if kind == "binary_fatal":
                    if a in ("y", "n"):
                        rec[key] = (a == "y")
                        break
                elif a in ("0", "1", "2"):
                    rec[key] = int(a)
                    break
                elif a == "na":
                    rec[key] = None
                    break
                print("    ? enter 0/1/2 (or y/n), 'na', 's' to skip, 'q' to quit")
            if quit_now or not rec:
                break

        if quit_now:
            print("\nsaved. resume with --resume")
            return
        if not rec:
            continue

        rec["notes"] = input("  free note (optional) > ").strip() or None
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print("  saved.")


def screen_score(rec: dict) -> float | None:
    """
    One number per screen, in [0,1].
    A violated constraint zeroes the screen — not a deduction, a zero. A modesty
    exclusion breached at position four is not 80% good.
    """
    if rec.get("constraint") is True:
        return 0.0
    parts = [rec.get(k) for k in ("would_save", "contrast", "completeness")
             if rec.get(k) is not None]
    if not parts:
        return None
    return sum(parts) / (2 * len(parts))


def report() -> None:
    rows: dict[str, list[dict]] = {}
    for p in sorted(RESULTS.glob("*.jsonl")) if RESULTS.exists() else []:
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        if recs:
            rows[p.stem] = recs
    if not rows:
        sys.exit("no baseline scores yet — run --engine <name> first")

    classes = sorted({r["class"] for recs in rows.values() for r in recs})

    print("\n## Overall\n")
    print("| engine | n | screen score | constraint violations |")
    print("|---|---|---|---|")
    for eng, recs in rows.items():
        ss = [s for r in recs if (s := screen_score(r)) is not None]
        viol = sum(1 for r in recs if r.get("constraint") is True)
        checked = sum(1 for r in recs if r.get("constraint") is not None)
        print(f"| {eng} | {len(recs)} | {statistics.mean(ss):.2f} | "
              f"{viol}/{checked} |" if ss else f"| {eng} | {len(recs)} | — | — |")

    print("\n## By class\n")
    print("| engine | " + " | ".join(classes) + " |")
    print("|" + "---|" * (len(classes) + 1))
    for eng, recs in rows.items():
        cells = []
        for c in classes:
            ss = [s for r in recs if r["class"] == c
                  and (s := screen_score(r)) is not None]
            cells.append(f"{statistics.mean(ss):.2f}" if ss else "—")
        print(f"| {eng} | " + " | ".join(cells) + " |")

    print("\nRead the class table, not the overall number. Losing `expected_losses`")
    print("is fine and planned. Losing `negation` or `completeness` is not — those")
    print("are the two classes the product is differentiated on.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=ENGINES)
    ap.add_argument("--class", dest="klass", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    if a.report:
        report()
    elif a.engine:
        run(a.engine, a.klass, a.resume)
    else:
        ap.error("need --engine or --report")


if __name__ == "__main__":
    main()

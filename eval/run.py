"""
The runner. This is the artefact that converts "should we use open models?" from
a debate into a table.

  python -m eval.run --providers sonnet,haiku,gpt56 --golden eval/golden_set
  python -m eval.run --providers sonnet --only mirror_selfie   # slice by tag
  python -m eval.run --replay runs/2026-08-06_sonnet.jsonl     # rescore, no spend

Outputs a markdown table to stdout and a jsonl of every decode to runs/.
Nothing ships red.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from decode import providers as P                      # noqa: E402
from decode.pipeline import DecodeEngine, coerce, load_vocab   # noqa: E402
from eval.score import LookResult, score_look, summarise, RunSummary  # noqa: E402


def load_golden(d: Path, only_tag: str | None = None,
                distribution: str | None = None) -> list[dict]:
    items = []
    vocab = load_vocab()
    for f in sorted(d.glob("*.json")):
        g = json.loads(f.read_text())
        # Golden labels arrive from both the interactive tool and hand-authored
        # review files. Give multi-fields with an explicit `none` value the same
        # canonical form as model output before score_look sees them.
        for garment in g.get("garments", []):
            for name, spec in vocab["fields"].items():
                if spec["kind"] != "multi" or name not in garment:
                    continue
                value, clean = coerce(vocab, name, garment[name])
                if clean:
                    garment[name] = value
        if only_tag and only_tag not in g.get("tags", []):
            continue
        if distribution and g.get("distribution") != distribution:
            continue
        img = d / g["image"]
        if not img.exists():
            print(f"  ! missing image for {g['image_id']}: {img}", file=sys.stderr)
            continue
        g["_image_path"] = img
        items.append(g)
    return items


def flatten(decode) -> dict:
    """Decode object -> the flat shape the scorer expects."""
    gs = []
    for g in decode.garments:
        row = {"role": g.role, "_conf": {}}
        for k, a in g.attrs.items():
            row[k] = a.value
            row["_conf"][k] = a.confidence
        gs.append(row)
    return {"garments": gs, "ocr": decode.dict()["ocr"], "cost_usd": decode.cost_usd,
            "latency_ms": decode.latency_ms, "state": decode.state()}


def run_provider(alias: str, golden: list[dict], vocab: dict,
                 out: Path, workers: int = 4) -> list[LookResult]:
    prov = P.get(alias)
    engine = DecodeEngine(prov, vocab, log_dir=ROOT / "runs" / "logs")
    results: list[LookResult] = []

    def one(item):
        try:
            img = item["_image_path"].read_bytes()
            d = engine.decode(img, caption=item.get("caption"))
            pred = flatten(d)
            r = score_look(vocab, pred, item)
            with open(out, "a") as f:
                f.write(json.dumps({"provider": alias, "image_id": item["image_id"],
                                    "pred": pred, "score": r.score,
                                    "hard_fails": r.hard_fails}) + "\n")
            return r
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return LookResult(item.get("image_id", "?"), 0, 0, 0, 0, 0, 0, error=str(e))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(one, golden):
            results.append(r)
            mark = "." if r.error is None and r.hard_fails == 0 else ("!" if r.hard_fails else "E")
            print(mark, end="", flush=True)
    print()
    return results


def table(summaries: list[RunSummary]) -> str:
    hdr = ("| model | n | attr | detect F1 | hard-fail | calib gap | hi-conf acc "
           "| $/decode | p50 ms | p90 ms | gate |")
    sep = "|" + "---|" * 11
    rows = [hdr, sep]
    for s in summaries:
        ok, fails = s.gate()
        rows.append(
            f"| {s.provider} | {s.n} | {s.attribute_score:.3f} | {s.detection_f1:.3f} "
            f"| {s.hard_fail_rate:.3f} | {s.calibration_gap:.3f} | {s.high_conf_accuracy:.3f} "
            f"| ${s.cost_per_decode:.4f} | {s.p50_latency_ms} | {s.p90_latency_ms} "
            f"| {'PASS' if ok else 'FAIL'} |")
    out = ["\n".join(rows), ""]

    fields = sorted({k for s in summaries for k in s.per_field})
    if fields:
        out.append("Per-field accuracy (where the work is):\n")
        out.append("| model | " + " | ".join(fields) + " |")
        out.append("|" + "---|" * (len(fields) + 1))
        for s in summaries:
            out.append("| " + s.provider + " | " +
                       " | ".join(f"{s.per_field.get(f, 0):.2f}" for f in fields) + " |")
        out.append("")

    for s in summaries:
        ok, fails = s.gate()
        if not ok:
            out.append(f"**{s.provider} blocked:** " + "; ".join(fails))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="sonnet")
    ap.add_argument("--golden", default=str(ROOT / "eval" / "golden_set"))
    ap.add_argument("--only", default=None, help="filter golden set by tag")
    ap.add_argument("--distribution", choices=["product_page", "inspiration"], default=None,
                    help="filter golden set by source distribution")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    vocab = load_vocab()
    golden = load_golden(Path(args.golden), args.only, args.distribution)
    if not golden:
        sys.exit("no golden items found")
    print(f"golden set: {len(golden)} looks, "
          f"{sum(len(g['garments']) for g in golden)} garments\n")

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    outdir = ROOT / "runs"
    outdir.mkdir(exist_ok=True)

    summaries = []
    for alias in args.providers.split(","):
        alias = alias.strip()
        print(f"{alias}: ", end="", flush=True)
        out = Path(args.out) if args.out else outdir / f"{stamp}_{alias}.jsonl"
        res = run_provider(alias, golden, vocab, out, args.workers)
        summaries.append(summarise(alias, res))

    print()
    print(table(summaries))
    if not any(s.gate()[0] for s in summaries):
        sys.exit(1)          # CI-friendly: nothing green, nothing ships


if __name__ == "__main__":
    main()

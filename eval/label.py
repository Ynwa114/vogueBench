"""
Golden-set labelling CLI.

The golden set is the bottleneck, not the code. 300 looks pulled from real saved
collections — mirror selfies, warm light, half-cropped garments, screenshots of
screenshots — not clean e-commerce photography. Labelling from scratch is slow;
labelling by CORRECTING a model's read is roughly 4x faster and produces exactly
the correction pairs the post-training dataset needs later. So this tool
pre-fills with a decode and asks the editor to fix it.

  python -m eval.label --images inbox/ --provider sonnet --labeller editor_01
  python -m eval.label --images inbox/ --blank          # no pre-fill, cold labelling

Discipline that makes the set worth having:
  - Pre-fill is a DRAFT. If the labeller just presses enter through everything,
    the golden set becomes a copy of the model and the gate measures nothing.
    Every 10th item is served blank (no pre-fill) as an attention check, and the
    agreement rate between blind and pre-filled labels is reported.
  - Two labellers on 10% of items -> inter-rater agreement per field. A field
    where your own editors disagree 30% of the time is a VOCABULARY bug, not a
    model bug, and no amount of prompt work will fix it.
  - Label each garment as if it were alone on its own product page. Occasion and
    vibe are garment-intrinsic labels; put outfit-level context in look tags.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from decode.pipeline import load_vocab  # noqa: E402


def ask_single(field: str, values: list[str], default: str | None) -> str | None:
    cols, line = [], ""
    for i, v in enumerate(values):
        cell = f"{i:>2}) {v:<20}"
        line += cell
        if len(line) > 90:
            cols.append(line); line = ""
    if line:
        cols.append(line)
    print(f"\n  {field}" + (f"   [draft: {default}]" if default else ""))
    print("\n".join("    " + c for c in cols))
    raw = input("  > ").strip()
    if raw == "":
        return default
    if raw == "-":
        return None
    if raw.isdigit() and int(raw) < len(values):
        return values[int(raw)]
    return raw if raw in values else default


def ask_multi(field: str, values: list[str], default: list[str] | None) -> list[str]:
    print(f"\n  {field} (comma-separated indices)" +
          (f"   [draft: {', '.join(default or [])}]" if default else ""))
    for i, v in enumerate(values):
        print(f"    {i:>2}) {v}", end="" if (i + 1) % 4 else "\n")
    print()
    raw = input("  > ").strip()
    if raw == "":
        return default or []
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.isdigit() and int(tok) < len(values):
            out.append(values[int(tok)])
        elif tok in values:
            out.append(tok)
    return out


def label_garment(vocab: dict, role: str, draft: dict | None) -> dict:
    g = {"role": role}
    for name, spec in vocab["fields"].items():
        category = g.get("category") or (draft or {}).get("category")
        if spec.get("applies_to") and category not in spec["applies_to"]:
            continue
        d = (draft or {}).get(name)
        if spec["kind"] == "multi":
            g[name] = ask_multi(name, spec["values"], d)
        else:
            v = ask_single(name, spec["values"], d)
            if v is not None:
                g[name] = v
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", default=str(ROOT / "eval" / "golden_set"))
    ap.add_argument("--provider", default=None, help="alias to pre-fill drafts with")
    ap.add_argument("--blank", action="store_true", help="never pre-fill")
    ap.add_argument("--labeller", default="editor_01")
    ap.add_argument("--blind-every", type=int, default=10)
    args = ap.parse_args()

    vocab = load_vocab()
    out = Path(args.out); (out / "images").mkdir(parents=True, exist_ok=True)
    imgs = [p for p in sorted(Path(args.images).iterdir())
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    print(f"{len(imgs)} images to label. Enter = accept draft, '-' = clear, "
          f"'s' = skip look, ctrl-c = stop.\n")

    engine = None
    if args.provider and not args.blank:
        from decode.providers import get
        from decode.pipeline import DecodeEngine
        engine = DecodeEngine(get(args.provider), vocab)

    roles = vocab["garment_roles"]
    for n, img in enumerate(imgs):
        iid = img.stem
        dest = out / f"{iid}.json"
        if dest.exists():
            print(f"skip {iid} (already labelled)")
            continue

        blind = engine is None or (n % args.blind_every == 0)
        print("\n" + "=" * 70)
        print(f"[{n + 1}/{len(imgs)}] {img.name}   {'(BLIND — no draft)' if blind else ''}")
        print(f"open: {img.resolve()}")
        caption = input("caption / alt text (blank if none): ").strip() or None
        tags = [t.strip() for t in
                input("tags (mirror_selfie, warm_light, crowded, screenshot...): ").split(",")
                if t.strip()]

        drafts: list[dict] = []
        if not blind:
            try:
                d = engine.decode(img.read_bytes(), caption=caption)
                drafts = [{**{k: a.value for k, a in g.attrs.items()}, "role": g.role}
                          for g in d.garments]
                print(f"  draft: {len(drafts)} garments — "
                      f"{', '.join(g.get('category', '?') for g in drafts)}")
            except Exception as e:
                print(f"  draft failed ({e}); labelling blind")

        garments = []
        while True:
            i = len(garments)
            d = drafts[i] if i < len(drafts) else None
            suggested = d["role"] if d else (roles[0] if i == 0 else "")
            print("  Label occasion and vibe for the garment alone, not the full outfit.")
            r = input(f"\nGARMENT {i + 1} role {roles} "
                      f"[{suggested}] (blank=done, 's'=skip look): ").strip()
            if r == "s":
                garments = None
                break
            if r == "" and (i > 0 or not suggested):
                break
            garments.append(label_garment(vocab, r or suggested, d))
        if garments is None:
            continue

        rec = {"image_id": iid, "image": f"images/{img.name}", "caption": caption,
               "tags": tags + (["blind_labelled"] if blind else ["draft_corrected"]),
               "labelled_by": args.labeller, "labelled_at": str(date.today()),
               "garments": garments}
        (out / "images" / img.name).write_bytes(img.read_bytes())
        dest.write_text(json.dumps(rec, indent=2))
        print(f"  saved {dest.name}  ({len(garments)} garments)")


if __name__ == "__main__":
    main()

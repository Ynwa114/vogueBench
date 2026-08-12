"""
The gate.

Scoring a decode is not "did the JSON parse". It is three separate questions,
scored separately because they fail for different reasons and get fixed by
different work:

  1. GARMENT DETECTION — did we find the right things to read?
     (fixed by the scene prompt / cropping)
  2. ATTRIBUTE ACCURACY — having found them, did we read them right?
     (fixed by the vocabulary, the garment prompt, or the model)
  3. CALIBRATION — when we were confident, were we right?
     (fixed by prompt wording; this is what licenses the confidence cascade)

A model that scores 0.82 with garbage calibration is more dangerous than one that
scores 0.78 honestly, because the cascade cannot use it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Field-level
# --------------------------------------------------------------------------- #

def _near_groups(spec: dict) -> list[set]:
    return [set(g) for g in spec.get("near", [])]


def _multi_values(spec: dict, value: Any) -> set:
    """Canonical form for a multi-valued field at scoring boundaries."""
    values = set(value or [])
    return {"none"} if not values and "none" in spec["values"] else values


def field_score(vocab: dict, name: str, pred: Any, gold: Any) -> float:
    """0.0–1.0 for one field of one garment."""
    spec = vocab["fields"][name]
    credit = vocab.get("near_credit", 0.5)

    if spec["kind"] == "multi":
        p, g = _multi_values(spec, pred), _multi_values(spec, gold)
        if not p and not g:
            return 1.0
        if not p or not g:
            return 0.0
        inter = len(p & g)
        prec, rec = inter / len(p), inter / len(g)
        return 0.0 if inter == 0 else 2 * prec * rec / (prec + rec)

    if pred is None or gold is None:
        return 1.0 if pred == gold else 0.0
    if pred == gold:
        return 1.0
    for grp in _near_groups(spec):
        if pred in grp and gold in grp:
            return credit
    return 0.0


def garment_score(vocab: dict, pred_g, gold_g) -> tuple[float, dict[str, float], bool]:
    """
    Returns (weighted score, per-field scores, hard_fail).
    A hard field wrong (category) zeroes the garment: showing trousers for a
    dress is not a partial success, it is the failure the product cannot survive.
    """
    per, num, den, hard_fail = {}, 0.0, 0.0, False
    for name, spec in vocab["fields"].items():
        if name not in gold_g:
            continue
        s = field_score(vocab, name, pred_g.get(name) if pred_g else None, gold_g[name])
        per[name] = s
        if spec.get("hard") and s < 1.0:
            hard_fail = True
        w = spec.get("weight", 0.0)
        num += s * w
        den += w
    total = 0.0 if hard_fail else (num / den if den else 0.0)
    return total, per, hard_fail


# --------------------------------------------------------------------------- #
# Look-level: align predicted garments to gold garments first
# --------------------------------------------------------------------------- #

def align(vocab: dict, preds: list[dict], golds: list[dict]) -> list[tuple[int | None, int | None]]:
    """
    Greedy best-match on role first, then on raw field agreement. Small N (<=6),
    so greedy is optimal enough and stays readable — an assignment solver here
    would be cleverness with no payoff.
    """
    pairs, used_p = [], set()
    for gi, g in enumerate(golds):
        best, best_s = None, -1.0
        for pi, p in enumerate(preds):
            if pi in used_p:
                continue
            s = 1.0 if p.get("role") == g.get("role") else 0.0
            s += garment_score(vocab, p, g)[0]
            if p.get("category") == g.get("category"):
                s += 1.0
            if s > best_s:
                best, best_s = pi, s
        if best is not None and best_s > 0.5:
            used_p.add(best)
            pairs.append((best, gi))
        else:
            pairs.append((None, gi))          # miss
    for pi in range(len(preds)):
        if pi not in used_p:
            pairs.append((pi, None))          # hallucinated garment
    return pairs


@dataclass
class LookResult:
    image_id: str
    score: float                  # attribute accuracy over matched garments
    detection_f1: float
    hard_fails: int
    matched: int
    missed: int
    spurious: int
    per_field: dict[str, list[float]] = field(default_factory=dict)
    calibration: list[tuple[float, float]] = field(default_factory=list)  # (confidence, correct)
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None


def score_look(vocab: dict, pred: dict, gold: dict) -> LookResult:
    """
    pred: {"garments": [{role, category, ..., "_conf": {field: c}}], "cost_usd":, "latency_ms":}
    gold: {"image_id":, "garments": [{role, category, ...}]}
    """
    preds, golds = pred.get("garments", []), gold.get("garments", [])
    pairs = align(vocab, preds, golds)

    scores, per_field, calib = [], {}, []
    hard, matched, missed, spurious = 0, 0, 0, 0

    for pi, gi in pairs:
        if gi is None:
            spurious += 1
            continue
        if pi is None:
            missed += 1
            continue
        matched += 1
        p, g = preds[pi], golds[gi]
        s, per, hf = garment_score(vocab, p, g)
        scores.append(s)
        hard += int(hf)
        for k, v in per.items():
            per_field.setdefault(k, []).append(v)
            c = (p.get("_conf") or {}).get(k)
            if c is not None:
                calib.append((float(c), v))

    tp = matched
    prec = tp / len(preds) if preds else 0.0
    rec = tp / len(golds) if golds else 0.0
    f1 = 0.0 if tp == 0 else 2 * prec * rec / (prec + rec)

    return LookResult(
        image_id=gold.get("image_id", "?"),
        score=sum(scores) / len(scores) if scores else 0.0,
        detection_f1=f1, hard_fails=hard, matched=matched,
        missed=missed, spurious=spurious, per_field=per_field, calibration=calib,
        cost_usd=pred.get("cost_usd", 0.0), latency_ms=pred.get("latency_ms", 0),
    )


# --------------------------------------------------------------------------- #
# Run-level aggregation + the gate
# --------------------------------------------------------------------------- #

GATE = {
    "attribute_score": 0.80,     # mean weighted accuracy on matched garments
    "detection_f1": 0.85,        # did we find the garments at all
    "hard_fail_rate": 0.03,      # category wrong on <=3% of garments read
    "calibration_gap": 0.15,     # |mean confidence - mean accuracy| when conf>=0.8
}


@dataclass
class RunSummary:
    provider: str
    n: int
    attribute_score: float
    detection_f1: float
    hard_fail_rate: float
    calibration_gap: float
    high_conf_accuracy: float
    per_field: dict[str, float]
    cost_per_decode: float
    p50_latency_ms: int
    p90_latency_ms: int
    errors: int

    def gate(self) -> tuple[bool, list[str]]:
        fails = []
        if self.attribute_score < GATE["attribute_score"]:
            fails.append(f"attribute_score {self.attribute_score:.3f} < {GATE['attribute_score']}")
        if self.detection_f1 < GATE["detection_f1"]:
            fails.append(f"detection_f1 {self.detection_f1:.3f} < {GATE['detection_f1']}")
        if self.hard_fail_rate > GATE["hard_fail_rate"]:
            fails.append(f"hard_fail_rate {self.hard_fail_rate:.3f} > {GATE['hard_fail_rate']}")
        if self.calibration_gap > GATE["calibration_gap"]:
            fails.append(f"calibration_gap {self.calibration_gap:.3f} > {GATE['calibration_gap']}")
        return (not fails), fails


def _pct(xs: list[int], q: float) -> int:
    if not xs:
        return 0
    s = sorted(xs)
    return s[min(int(q * len(s)), len(s) - 1)]


def summarise(provider: str, results: list[LookResult]) -> RunSummary:
    ok = [r for r in results if r.error is None]
    n = len(ok)
    if n == 0:
        return RunSummary(provider, 0, 0, 0, 1, 1, 0, {}, 0, 0, 0, len(results))

    per_field: dict[str, float] = {}
    for r in ok:
        for k, vs in r.per_field.items():
            per_field.setdefault(k, [])
            per_field[k].extend(vs)
    per_field = {k: sum(v) / len(v) for k, v in per_field.items()}

    total_garments = sum(r.matched for r in ok) or 1
    calib = [c for r in ok for c in r.calibration]
    hi = [(c, s) for c, s in calib if c >= 0.8]
    hi_acc = sum(s for _, s in hi) / len(hi) if hi else 0.0
    hi_conf = sum(c for c, _ in hi) / len(hi) if hi else 0.0

    return RunSummary(
        provider=provider,
        n=n,
        attribute_score=sum(r.score for r in ok) / n,
        detection_f1=sum(r.detection_f1 for r in ok) / n,
        hard_fail_rate=sum(r.hard_fails for r in ok) / total_garments,
        calibration_gap=abs(hi_conf - hi_acc) if hi else 1.0,
        high_conf_accuracy=hi_acc,
        per_field=per_field,
        cost_per_decode=sum(r.cost_usd for r in ok) / n,
        p50_latency_ms=_pct([r.latency_ms for r in ok], 0.5),
        p90_latency_ms=_pct([r.latency_ms for r in ok], 0.9),
        errors=len(results) - n,
    )

"""
Resolution telemetry.

Tracks how each piece of a query got understood. The headline number is tier-1
hit rate, but the more useful artefact is the miss log: every fragment we failed
to ground, counted by frequency.

That log IS the predicate backlog. You do not need to guess which predicates to
write next, or mine autocomplete for candidates — your own users tell you, ranked
by real demand, for free. A phrase that 40 women typed last week is worth
grounding today; one that appeared once can wait.

Granularity is per-FRAGMENT, not per-query, because queries are partially
understood far more often than they are wholly understood or wholly missed.
"logged a miss on this query" tells you nothing actionable; "logged a miss on
'says have taste' 63 times" is a work item.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal

Tier = Literal["exact", "semantic", "vocab", "miss"]

# Tier meanings:
#   exact     predicate matched by literal utterance        (<1ms, free)
#   semantic  predicate matched by utterance embedding      (~5ms, small model)
#   vocab     bare vocabulary term, no predicate needed     (<1ms, free)
#   miss      nothing matched -> grounding proposal queued  (LLM, async, once ever)


@dataclass
class Resolution:
    fragment: str
    tier: Tier
    resolved_to: str | None = None      # predicate or vocab field
    similarity: float | None = None     # semantic tier only
    lane: str | None = None


@dataclass
class QueryResolution:
    query: str
    resolutions: list[Resolution]
    ts: str = ""
    session_id: str | None = None

    @property
    def fragment_coverage(self) -> float:
        """Fraction of meaningful fragments understood at all."""
        if not self.resolutions:
            return 1.0
        hit = sum(1 for r in self.resolutions if r.tier != "miss")
        return hit / len(self.resolutions)

    @property
    def fully_resolved(self) -> bool:
        return all(r.tier != "miss" for r in self.resolutions)

    @property
    def cache_hit(self) -> bool:
        """
        The flywheel number. True when NOTHING needed a model — every fragment
        resolved from cached knowledge. This is what should climb over time.
        """
        return all(r.tier in ("exact", "vocab") for r in self.resolutions)


class ResolutionLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, qr: QueryResolution) -> None:
        qr.ts = qr.ts or datetime.utcnow().isoformat()
        rec = asdict(qr)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def read(self) -> list[QueryResolution]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(QueryResolution(
                query=d["query"],
                resolutions=[Resolution(**r) for r in d["resolutions"]],
                ts=d.get("ts", ""), session_id=d.get("session_id")))
        return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _day(ts: str) -> str:
    return (ts or "")[:10] or str(date.today())


def hit_rate_over_time(log: ResolutionLog, bucket: str = "day") -> list[tuple[str, int, float, float]]:
    """(period, n_queries, cache_hit_rate, mean_fragment_resolution) — the flywheel curve."""
    rows = log.read()
    buckets: dict[str, list[QueryResolution]] = {}
    for r in rows:
        key = _day(r.ts)
        if bucket == "week":
            try:
                d = datetime.fromisoformat(r.ts)
                key = f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
            except ValueError:
                pass
        buckets.setdefault(key, []).append(r)

    out = []
    for k in sorted(buckets):
        qs = buckets[k]
        out.append((k, len(qs),
                    sum(q.cache_hit for q in qs) / len(qs),
                    sum(q.fragment_coverage for q in qs) / len(qs)))
    return out


def miss_backlog(log: ResolutionLog, min_count: int = 2) -> list[tuple[str, int, list[str]]]:
    """
    The work queue. Missed fragments by frequency, with example queries.
    Normalises lightly so 'not too shiny' and 'not too shiny!' are one item.
    """
    counts: Counter = Counter()
    examples: dict[str, list[str]] = {}
    for qr in log.read():
        for r in qr.resolutions:
            if r.tier != "miss":
                continue
            key = re.sub(r"\s+", " ", r.fragment.strip().lower())
            counts[key] += 1
            examples.setdefault(key, [])
            if len(examples[key]) < 3 and qr.query not in examples[key]:
                examples[key].append(qr.query)
    return [(f, c, examples[f]) for f, c in counts.most_common() if c >= min_count]


def tier_mix(log: ResolutionLog) -> dict[str, float]:
    c: Counter = Counter()
    for qr in log.read():
        for r in qr.resolutions:
            c[r.tier] += 1
    total = sum(c.values()) or 1
    return {k: v / total for k, v in c.most_common()}


def report(log: ResolutionLog) -> str:
    rows = log.read()
    if not rows:
        return "no resolutions logged yet"

    lines = ["## Flywheel — cache hit rate over time\n",
             "| period | queries | cache hit | fragment resolution |", "|---|---|---|---|"]
    for period, n, hit, cov in hit_rate_over_time(log):
        lines.append(f"| {period} | {n} | {hit:.0%} | {cov:.0%} |")

    mix = tier_mix(log)
    lines += ["", "## Tier mix (all fragments)\n",
              "| tier | share |", "|---|---|"]
    for t in ("exact", "vocab", "semantic", "miss"):
        if t in mix:
            lines.append(f"| {t} | {mix[t]:.0%} |")

    backlog = miss_backlog(log)
    lines += ["", f"## Predicate backlog — {len(backlog)} phrases seen 2+ times\n",
              "| fragment | seen | example query |", "|---|---|---|"]
    for frag, n, ex in backlog[:25]:
        lines.append(f"| {frag} | {n} | {ex[0] if ex else ''} |")

    lines += ["",
              "Ground the top of that backlog first — it is demand-ordered, which is",
              "strictly better than mining autocomplete for phrases nobody typed here.",
              "",
              "Caveat worth remembering: cache hit rate is gameable. A predicate that",
              "matches everything raises it and helps nobody. Always read it next to",
              "the TWIN-FASHION-90 class scores — hit rate climbing while benchmark",
              "quality is flat means predicates are being grounded badly, not that the",
              "flywheel is working."]
    return "\n".join(lines)

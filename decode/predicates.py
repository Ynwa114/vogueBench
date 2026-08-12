"""
The predicate engine.

This is the piece that separates a semantic search box from a reasoning engine.
A query is not matched against products. It is decomposed into predicates, each
predicate is grounded in clauses over observable attributes, and the clauses
compile to a filter that a database can execute.

Three lanes, and which lane a predicate lands in is the whole design:

    gate     ALL must hold.     Correctness. "beach"
    exclude  ANY match kills.   Constraints. "not too revealing"
    rank     Scores only.       Degree.      "not too basic"

The failure this prevents: putting a hard constraint in the rank lane. A constraint
satisfied 80% of the time is not 80% good, it is broken — the user
who said "not too revealing" and got a cutout at position four does not file a
relevance complaint, she stops opening the app.

The other failure it prevents: negation via vector arithmetic. "not beige"
embeds CLOSER to beige. Negations must leave the vector space entirely and
become symbolic exclusions before ANN runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

from decode.resolution import Resolution

PRED_PATH = Path(__file__).resolve().parent.parent / "predicates.yaml"

Lane = Literal["gate", "exclude", "rank"]
KIND_TO_LANE: dict[str, Lane] = {"require": "gate", "exclude": "exclude", "prefer": "rank"}


# --------------------------------------------------------------------------- #
# Clause AST
# --------------------------------------------------------------------------- #

@dataclass
class Cmp:
    """field OP value — the leaf of the grammar."""
    field: str
    op: str            # in | not in | == | != | >= | <= | > | <
    value: Any

    def evaluate(self, product: dict) -> bool:
        got = product.get(self.field)
        if got is None:
            return False
        if self.op == "in":
            vals = got if isinstance(got, list) else [got]
            return any(v in self.value for v in vals)
        if self.op == "not in":
            vals = got if isinstance(got, list) else [got]
            return all(v not in self.value for v in vals)
        if self.op == "==":
            return got == self.value
        if self.op == "!=":
            return got != self.value
        try:
            g, v = float(got), float(self.value)
        except (TypeError, ValueError):
            return False
        return {">=": g >= v, "<=": g <= v, ">": g > v, "<": g < v}[self.op]

    def sql(self, params: list) -> str:
        if self.op in ("in", "not in"):
            params.append(list(self.value))
            neg = "NOT " if self.op == "not in" else ""
            return f"{neg}({self.field} = ANY(${len(params)}))"
        params.append(self.value)
        return f"{self.field} {self.op} ${len(params)}"


@dataclass
class AnyOf:
    clauses: list
    def evaluate(self, p: dict) -> bool:
        return any(c.evaluate(p) for c in self.clauses)
    def sql(self, params: list) -> str:
        return "(" + " OR ".join(c.sql(params) for c in self.clauses) + ")"


@dataclass
class AllOf:
    clauses: list
    def evaluate(self, p: dict) -> bool:
        return all(c.evaluate(p) for c in self.clauses)
    def sql(self, params: list) -> str:
        return "(" + " AND ".join(c.sql(params) for c in self.clauses) + ")"


# --------------------------------------------------------------------------- #
# Parser — string clause to AST. Tiny by design.
# --------------------------------------------------------------------------- #

_LIST = re.compile(r"^\s*(\w+)\s+(not in|in)\s+\[(.*)\]\s*$")
_CMP = re.compile(r"^\s*(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


def parse_clause(node: Any) -> Any:
    """Accepts a string leaf, or a dict/one-key-dict of any_of / all_of."""
    if isinstance(node, dict):
        if len(node) != 1:
            raise ValueError(f"clause dict must have exactly one key: {node}")
        k, v = next(iter(node.items()))
        if k == "any_of":
            return AnyOf([parse_clause(c) for c in v])
        if k == "all_of":
            return AllOf([parse_clause(c) for c in v])
        raise ValueError(f"unknown clause key: {k}")

    s = str(node).strip()
    # YAML strings of the form "all_of: [a, b]" appear inside value lists
    if s.startswith(("any_of:", "all_of:")):
        return parse_clause(yaml.safe_load(s))

    m = _LIST.match(s)
    if m:
        fname, op, body = m.group(1), m.group(2), m.group(3)
        vals = [v.strip().strip("'\"") for v in body.split(",") if v.strip()]
        return Cmp(fname, op, vals)

    m = _CMP.match(s)
    if m:
        fname, op, raw = m.groups()
        raw = raw.strip().strip("'\"")
        if raw in ("true", "false"):
            val: Any = raw == "true"
        else:
            try:
                val = float(raw)
            except ValueError:
                val = raw
        return Cmp(fname, op, val)

    raise ValueError(f"cannot parse clause: {s!r}")


# --------------------------------------------------------------------------- #
# Predicates
# --------------------------------------------------------------------------- #

@dataclass
class Predicate:
    name: str
    kind: str
    status: str
    utterances: list[str]
    grounding: Any                    # AST
    penalise: Any | None = None       # AST, rank lane only
    note: str | None = None
    approved_by: str | None = None

    @property
    def lane(self) -> Lane:
        return KIND_TO_LANE[self.kind]

    @property
    def usable_in_gate(self) -> bool:
        """Machine-proposed groundings never filter. They may only rank."""
        return self.status == "approved"

    def satisfied_by(self, product: dict) -> bool:
        return self.grounding.evaluate(product)

    def score(self, product: dict) -> float:
        """Rank-lane contribution in [-1, 1]."""
        s = 1.0 if self.grounding.evaluate(product) else 0.0
        if self.penalise is not None and self.penalise.evaluate(product):
            s -= 1.0
        return s


def _walk_clauses(node: Any) -> Iterable[Cmp]:
    if isinstance(node, Cmp):
        yield node
    elif isinstance(node, (AnyOf, AllOf)):
        for child in node.clauses:
            yield from _walk_clauses(child)


def validate_predicates(vocab: dict, predicates: dict[str, Predicate],
                        derived_fields: set[str] | None = None) -> None:
    """Fail fast when an approved rule references a removed field or value."""
    derived_fields = derived_fields or {"distinctiveness", "price_percentile"}
    errors = []
    for name, predicate in predicates.items():
        for clause in _walk_clauses(predicate.grounding):
            if clause.field in derived_fields:
                continue
            spec = vocab["fields"].get(clause.field)
            if spec is None:
                errors.append(f"{name}: unknown field {clause.field}")
                continue
            values = clause.value if clause.op in ("in", "not in") else [clause.value]
            invalid = [value for value in values if value not in spec["values"]]
            if invalid:
                errors.append(f"{name}: invalid {clause.field} value(s) {invalid}")
    if errors:
        raise ValueError("invalid predicate grounding: " + "; ".join(errors))


def load_predicates(path: Path | str = PRED_PATH, vocab: dict | None = None) -> dict[str, Predicate]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    out: dict[str, Predicate] = {}
    for name, body in raw["predicates"].items():
        out[name] = Predicate(
            name=name,
            kind=body["kind"],
            status=body.get("status", "proposed"),
            utterances=body.get("utterances", []),
            grounding=parse_clause(body["grounding"]),
            penalise=parse_clause(body["penalise"]) if body.get("penalise") else None,
            note=body.get("note"),
            approved_by=body.get("approved_by"),
        )
    if vocab is not None:
        validate_predicates(vocab, out, set(raw.get("derived_fields", {})))
    return out


# --------------------------------------------------------------------------- #
# Query state — the object the whole retrieval path passes around
# --------------------------------------------------------------------------- #

@dataclass
class QueryState:
    gate: dict[str, Any] = field(default_factory=dict)
    gate_predicates: list[str] = field(default_factory=list)
    exclude_attrs: dict[str, list] = field(default_factory=dict)
    exclude_predicates: list[str] = field(default_factory=list)
    rank_predicates: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)   # gaps -> grounding proposals
    resolutions: list = field(default_factory=list)       # telemetry, one per fragment
    text: str = ""

    def admits(self, product: dict, preds: dict[str, Predicate]) -> bool:
        """Hard pass/fail. Exclusions are checked FIRST and are never negotiable."""
        for name in self.exclude_predicates:
            p = preds.get(name)
            if p and p.usable_in_gate and p.satisfied_by(product):
                return False
        for fname, bad in self.exclude_attrs.items():
            got = product.get(fname)
            vals = got if isinstance(got, list) else [got]
            if any(v in bad for v in vals):
                return False
        for fname, want in self.gate.items():
            got = product.get(fname)
            if isinstance(want, list):
                vals = got if isinstance(got, list) else [got]
                if not any(v in want for v in vals):
                    return False
            elif got != want:
                return False
        for name in self.gate_predicates:
            p = preds.get(name)
            if p and p.usable_in_gate and not p.satisfied_by(product):
                return False
        return True

    def rank_score(self, product: dict, preds: dict[str, Predicate]) -> float:
        if not self.rank_predicates:
            return 0.0
        scores = [preds[n].score(product) for n in self.rank_predicates if n in preds]
        return sum(scores) / len(scores) if scores else 0.0

    def chips(self) -> dict[str, list[str]]:
        """What the drawer renders back at her. The UI and the query are one object."""
        return {
            "matching": [v for vals in self.gate.values()
                         for v in (vals if isinstance(vals, list) else [vals])]
                        + [n.replace("_", " ") for n in self.gate_predicates],
            "excluding": [v for vals in self.exclude_attrs.values() for v in vals]
                         + [n.replace("_", " ") for n in self.exclude_predicates],
            "preferring": [n.replace("_", " ") for n in self.rank_predicates],
        }


# --------------------------------------------------------------------------- #
# Query parsing — utterance matching + symbolic negation
# --------------------------------------------------------------------------- #

NEG_CUES = ["not too", "not very", "nothing", "without", "no ", "not ", "isn't", "avoid",
            "but not", "except"]


def _negation_spans(text: str) -> list[tuple[int, int]]:
    """Character spans under negation scope. Scope ends at a comma or conjunction."""
    spans, low = [], text.lower()
    for cue in NEG_CUES:
        start = 0
        while (i := low.find(cue, start)) != -1:
            end = len(low)
            for stop in [",", " and ", " with ", ";"]:
                j = low.find(stop, i + len(cue))
                if j != -1:
                    end = min(end, j)
            spans.append((i, end))
            start = i + len(cue)
    return spans


def parse_query(text: str, vocab: dict, preds: dict[str, Predicate]) -> QueryState:
    """
    Deterministic first pass. An LLM refines what this can't resolve, but everything
    this catches is caught for free, identically, every time — which matters because
    a constraint that resolves non-deterministically is not a constraint.
    """
    low = text.lower()
    qs = QueryState(text=text)
    neg = _negation_spans(low)

    def negated(pos: int) -> bool:
        return any(s <= pos < e for s, e in neg)

    # 1. predicates by utterance, longest first so "not too basic" beats "basic"
    hits = []
    for p in preds.values():
        for u in p.utterances:
            i = low.find(u.lower())
            if i != -1:
                hits.append((len(u), i, p))
    hits.sort(reverse=True, key=lambda h: h[0])

    claimed: list[tuple[int, int]] = []
    for length, pos, p in hits:
        if any(s <= pos < e for s, e in claimed):
            continue
        claimed.append((pos, pos + length))
        qs.resolutions.append(Resolution(
            fragment=low[pos:pos + length], tier="exact",
            resolved_to=p.name, lane=p.lane))
        if p.lane == "exclude":
            qs.exclude_predicates.append(p.name)
        elif p.lane == "gate":
            qs.gate_predicates.append(p.name)
        else:
            qs.rank_predicates.append(p.name)

    # 2. bare vocabulary terms, routed by negation scope
    for fname, spec in vocab["fields"].items():
        for val in spec["values"]:
            surface = val.replace("_", " ")
            # Word boundaries, not substring: 'hat' must not match inside 'that',
            # 'red' must not match inside 'ruched'. This class of bug produces a
            # plausible-looking wrong gate that nobody notices.
            m = re.search(rf"(?<!\w){re.escape(surface)}(?!\w)", low)
            if m is None or any(s <= m.start() < e for s, e in claimed):
                continue
            i = m.start()
            claimed.append((i, i + len(surface)))
            qs.resolutions.append(Resolution(
                fragment=surface, tier="vocab", resolved_to=fname,
                lane="exclude" if negated(i) else "gate"))
            if negated(i):
                # Exclusions are NOT expanded. "not black" means black, not charcoal —
                # over-excluding silently empties the shelf and she never learns why.
                qs.exclude_attrs.setdefault(fname, []).append(val)
            elif spec["kind"] == "single" and fname not in qs.gate:
                # Gates ARE expanded across near-groups. Typed language is colloquial:
                # "top" means the top family, not the exact enum member, so a tshirt
                # must survive a "white top" gate. The near groups already encode
                # exactly which confusions a stylist would forgive.
                family = {val}
                for grp in spec.get("near", []):
                    if val in grp:
                        family |= set(grp)
                qs.gate[fname] = sorted(family)

    # 3. anything meaningful the parser could not account for -> grounding gaps.
    #    Deliberately NOT limited to negations. "says I have taste" carries the
    #    entire intent of its query and matches nothing; dropping it silently is
    #    worse than failing loudly, because the shelf still looks plausible and
    #    nobody finds out the query was never understood.
    STOP = {"a", "an", "the", "for", "with", "that", "this", "some", "something",
            "me", "my", "i", "is", "are", "of", "in", "on", "to", "and", "or",
            "but", "it", "im", "want", "need", "looking", "show", "find", "get"}

    accounted = sorted(claimed)
    cursor, spans = 0, []
    for s, e in accounted + [(len(low), len(low))]:
        if s > cursor:
            spans.append((cursor, s))
        cursor = max(cursor, e)

    for s, e in spans:
        frag = low[s:e]
        words = [w for w in re.findall(r"[a-z']+", frag) if w not in STOP]
        if len(words) >= 2:
            frag = " ".join(words)
            qs.unresolved.append(frag)
            qs.resolutions.append(Resolution(fragment=frag, tier="miss"))

    return qs


# --------------------------------------------------------------------------- #
# The gap loop — Onton's self-learning, with a human gate
# --------------------------------------------------------------------------- #

GROUNDING_PROMPT = """You ground fashion language into observable garment attributes.

An unknown phrase appeared in a shopper's query: "{phrase}"

Decompose it into attributes a tagger can verify from a product photo. Use ONLY
these fields and values:

{sheet}

Derived numeric fields also available: {derived}

Return strict JSON:
{{
  "kind": "require" | "exclude" | "prefer",
  "reasoning": "<one sentence: what would make an item satisfy this>",
  "grounding": {{"any_of": ["field in [a, b]", "..."]}},
  "penalise": {{"any_of": ["..."]}},
  "confidence": 0.0
}}

Rules that matter:
- Choose "exclude" ONLY for observable properties an item either has or lacks.
- Choose "prefer" for matters of DEGREE. "Not too basic" is a degree, not a
  property — no item is objectively basic, it is basic relative to its category.
  Excluding your way to "not basic" is the classic error; invert it into positive
  distinctive requirements instead.
- Choose "require" for context and occasion.
- Never ground a look-related phrase in price. "Looks expensive" is about the
  look, and usually the entire point is wanting it without the price.
"""


def propose_grounding(phrase: str, vocab: dict, provider) -> dict:
    """
    Called when parse_query returns an unresolved fragment. Output lands at
    status=proposed and CANNOT filter until an editor approves it — which is the
    single change that makes this an owned asset rather than an LLM guess.
    """
    sheet = "\n".join(f"- {k}: {', '.join(s['values'])}" for k, s in vocab["fields"].items())
    derived = "distinctiveness, price_percentile"
    prompt = GROUNDING_PROMPT.format(phrase=phrase, sheet=sheet, derived=derived)
    r = provider.see([], prompt, "You are precise and conservative.", max_tokens=700)
    body = r.json()
    body.update({"name": re.sub(r"\W+", "_", phrase.strip())[:40],
                 "status": "proposed", "utterances": [phrase],
                 "proposed_by": provider.name})
    return body

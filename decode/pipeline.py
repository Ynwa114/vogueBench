"""
The decode engine.

Shape (as specced): whole-image context pass, then per-garment reads against the
fixed vocabulary, with a confidence per attribute. Confidence is not decoration —
it drives three things downstream:

  1. the disambiguation line in chat ("reading this as satin — tell me if I'm
     wrong"), which is how a failure becomes a labelled training example;
  2. the result state (nailed it / confident read / attribute read);
  3. the escalation decision in the confidence cascade, once a small model is
     serving the first attempt.

Everything here is deterministic except the model call. Every model call goes
through providers.VisionProvider. Every call is logged with prompt + raw output +
model version, because from day one, inference spend is also dataset spend.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

VOCAB_PATH = Path(__file__).resolve().parent.parent / "vocab.yaml"


def load_vocab(path: Path | str = VOCAB_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Attr:
    value: Any
    confidence: float = 1.0


@dataclass
class Garment:
    role: str                      # outerwear / top / bottom / onepiece / footwear / bag / accessory
    attrs: dict[str, Attr] = field(default_factory=dict)
    brand: str | None = None       # only ever set from evidence, never from vibes
    brand_source: str | None = None  # caption | ocr | catalog_match | None
    notes: str | None = None

    def value(self, f: str):
        a = self.attrs.get(f)
        return a.value if a else None

    def conf(self, f: str) -> float:
        a = self.attrs.get(f)
        return a.confidence if a else 0.0


@dataclass
class Decode:
    decode_id: str
    garments: list[Garment]
    scene: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0

    def weakest(self, vocab: dict, threshold: float = 0.6) -> list[tuple[int, str, Any, float]]:
        """Attributes worth asking about. Ordered by (weight x uncertainty)."""
        out = []
        for i, g in enumerate(self.garments):
            for fname, spec in vocab["fields"].items():
                if fname not in g.attrs:
                    continue
                c = g.conf(fname)
                if c < threshold:
                    out.append((i, fname, g.value(fname), c, spec.get("weight", 0) * (1 - c)))
        out.sort(key=lambda r: -r[4])
        return [(i, f, v, c) for i, f, v, c, _ in out]

    def state(self) -> str:
        """Honest result state. Never claim a higher one than the evidence allows."""
        if any(g.brand and g.brand_source in ("caption", "catalog_match") for g in self.garments):
            return "nailed_it"
        mean = sum(g.conf("category") for g in self.garments) / max(len(self.garments), 1)
        return "confident_read" if mean >= 0.75 else "attribute_read"

    def dict(self):
        return asdict(self)


# --------------------------------------------------------------------------- #
# Prompts — generated FROM the vocabulary, never hand-maintained alongside it.
# --------------------------------------------------------------------------- #

SYSTEM = (
    "You read fashion images for a stylist product. You are precise, never "
    "flattering, and you never invent a brand. You answer only in the controlled "
    "vocabulary you are given, and you report honest confidence — a low confidence "
    "is useful to us, a confident wrong answer is expensive."
)


def scene_prompt(caption: str | None) -> str:
    cap = f"\n\nCaption / alt text that accompanied the image:\n\"\"\"{caption}\"\"\"" \
        if caption else ""
    return f"""Look at this image and describe the SCENE only. Do not describe garments in detail yet.

Return strict JSON:
{{
  "people": <int>,
  "primary_subject": "<which person, if several: e.g. 'woman centre-frame'>",
  "shot": "mirror_selfie | full_body | half_body | flat_lay | runway | street | product",
  "setting": "<3 words>",
  "lighting_risk": "<any condition that could mislead colour reading: 'warm indoor light', 'harsh flash', 'none'>",
  "garments": [
    {{"role": "outerwear|top|bottom|onepiece|footwear|bag|accessory",
      "locator": "<short phrase to find it again, e.g. 'cropped jacket over shoulders'>",
      "visibility": "full|partial|barely"}}
  ],
  "named_brands": ["<only brands literally stated in the caption or visible as text/logo in the image>"]
}}

List garments in reading order: outerwear, top, bottom, onepiece, footwear, bag, accessory.
Include a garment only if a user would plausibly want to shop it. Ignore garments on
non-primary subjects.{cap}"""


def garment_prompt(vocab: dict, role: str, locator: str, lighting_risk: str) -> str:
    lines = []
    for name, spec in vocab["fields"].items():
        applies = spec.get("applies_to")
        vals = " | ".join(spec["values"])
        kind = "choose ALL that apply" if spec["kind"] == "multi" else "choose ONE"
        note = f"  (only if category in {applies}, else return null)" if applies else ""
        lines.append(f'- {name}: {kind}{note}\n    {vals}')
    sheet = "\n".join(lines)
    warn = (f"\nColour warning: the shot has {lighting_risk}. If the colour could be "
            f"either of two neighbours, pick the more likely one and drop confidence "
            f"below 0.6 rather than guessing confidently.\n"
            if lighting_risk and lighting_risk != "none" else "")

    return f"""Read ONE garment: the {role} — "{locator}".

Fill every field from this controlled vocabulary. Use only listed values, exactly as spelled.
{sheet}
{warn}
For a field that does not apply to this garment category, return `null` for its
`value`; do not invent a filler reading. Those fields are excluded from scoring.
For every field give a confidence in [0,1]. Confidence means: "if a fashion editor
graded this, how likely am I right?" Be honest — 0.4 on a genuinely ambiguous fabric
is worth more to us than a confident guess.

Return strict JSON, no prose:
{{
  "category": {{"value": "...", "confidence": 0.0}},
  "silhouette": {{"value": "...", "confidence": 0.0}},
  "colour": {{"value": "...", "confidence": 0.0}},
  "pattern": {{"value": "...", "confidence": 0.0}},
  "surface_detail": {{"value": ["..."], "confidence": 0.0}},
  "fit_ease": {{"value": "...", "confidence": 0.0}},
  "fabric_look": {{"value": "...", "confidence": 0.0}},
  "neckline": {{"value": "...", "confidence": 0.0}},
  "sleeve_length": {{"value": "...", "confidence": 0.0}},
  "length": {{"value": "...", "confidence": 0.0}},
  "occasion": {{"value": ["..."], "confidence": 0.0}},
  "vibe": {{"value": ["..."], "confidence": 0.0}},
  "sheerness": {{"value": "...", "confidence": 0.0}},
  "search_phrase": "<how a shopper would type this into a search bar, <=8 words>"
}}

Never name a brand here. Brand comes from caption or catalogue matching, not from pixels."""


# --------------------------------------------------------------------------- #
# Caption mining — the answer key is often written under the photo.
# --------------------------------------------------------------------------- #

_BRAND_PAT = re.compile(r"(?:^|\s)@([A-Za-z0-9._]{2,30})|#([A-Za-z0-9]{3,30})")


def mine_caption(caption: str | None, known_brands: set[str] | None = None) -> dict:
    """Cheap, deterministic, and it frequently just tells you the answer."""
    if not caption:
        return {"handles": [], "hashtags": [], "brand_candidates": []}
    handles, tags = [], []
    for m in _BRAND_PAT.finditer(caption):
        (handles if m.group(1) else tags).append((m.group(1) or m.group(2)).lower())
    cands: dict[str, str] = {}          # normalised key -> canonical brand string
    if known_brands:
        low = caption.lower()
        for b in known_brands:
            key = b.lower().replace(" ", "")
            if b.lower() in low or key in handles or key in tags:
                cands[key] = b          # canonical casing wins over the @handle form
    return {"handles": handles, "hashtags": tags,
            "brand_candidates": sorted(cands.values())}


# --------------------------------------------------------------------------- #
# Validation — a value outside the vocabulary is a pipeline failure, not a decode.
# --------------------------------------------------------------------------- #

def coerce(vocab: dict, field_name: str, raw: Any) -> tuple[Any, bool]:
    spec = vocab["fields"][field_name]
    legal = set(spec["values"])
    if spec["kind"] == "multi":
        vals = raw if isinstance(raw, list) else [raw]
        keep = [str(v).strip().lower().replace(" ", "_") for v in vals]
        keep = [v for v in keep if v in legal]
        return keep, len(keep) == len(vals)
    v = str(raw).strip().lower().replace(" ", "_")
    return (v, True) if v in legal else (None, False)


# --------------------------------------------------------------------------- #
# The pipeline
# --------------------------------------------------------------------------- #

class DecodeEngine:
    def __init__(self, provider, vocab: dict | None = None, log_dir: Path | None = None):
        self.p = provider
        self.vocab = vocab or load_vocab()
        self.log_dir = Path(log_dir) if log_dir else None
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, decode_id: str, stage: str, prompt: str, resp) -> None:
        if not self.log_dir:
            return
        rec = {"decode_id": decode_id, "stage": stage, "model": resp.model,
               "prompt": prompt, "output": resp.text,
               "in_tok": resp.input_tokens, "out_tok": resp.output_tokens,
               "latency_ms": resp.latency_ms}
        with open(self.log_dir / "decodes.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")

    def _cost(self, r) -> float:
        return (r.input_tokens * self.p.price_in + r.output_tokens * self.p.price_out) / 1e6

    def decode(self, image: bytes, caption: str | None = None,
               known_brands: set[str] | None = None, max_garments: int = 6) -> Decode:
        did = uuid.uuid4().hex[:12]
        cost = 0.0
        latency = 0

        # --- pass 1: scene ---
        sp = scene_prompt(caption)
        r1 = self.p.see([image], sp, SYSTEM, max_tokens=900)
        self._log(did, "scene", sp, r1)
        cost += self._cost(r1); latency += r1.latency_ms
        scene = r1.json()

        mined = mine_caption(caption, known_brands)
        scene["caption_mined"] = mined
        # Merge the model's read of on-image/caption brand text with the deterministic
        # caption mine, deduped case-insensitively. Canonical casing from the known
        # brand list wins, because that string ends up on the product card.
        seen: dict[str, str] = {}
        for b in list(mined["brand_candidates"]) + list(scene.get("named_brands", [])):
            seen.setdefault(str(b).lower().replace(" ", ""), str(b))
        named = list(seen.values())

        # --- pass 2: one read per garment ---
        garments: list[Garment] = []
        for g in scene.get("garments", [])[:max_garments]:
            if g.get("visibility") == "barely":
                continue
            gp = garment_prompt(self.vocab, g.get("role", "top"),
                                g.get("locator", ""), scene.get("lighting_risk", "none"))
            r2 = self.p.see([image], gp, SYSTEM, max_tokens=800)
            self._log(did, f"garment:{g.get('role')}", gp, r2)
            cost += self._cost(r2); latency += r2.latency_ms
            body = r2.json()

            attrs: dict[str, Attr] = {}
            for fname in self.vocab["fields"]:
                cell = body.get(fname)
                if cell is None:
                    continue
                raw = cell.get("value") if isinstance(cell, dict) else cell
                conf = float(cell.get("confidence", 0.5)) if isinstance(cell, dict) else 0.5
                val, clean = coerce(self.vocab, fname, raw)
                if val is None or val == []:
                    continue
                attrs[fname] = Attr(val, conf if clean else min(conf, 0.5))

            # v0 attribution heuristic: exactly one brand named + this is the primary
            # garment -> claim it. Anything else stays unbranded, because a wrong
            # "this is Zara" is the single most expensive lie the product can tell.
            # TODO(v0.2): caption-span -> garment attribution ("dress @zara, shoes old").
            primary = not garments
            claim = len(named) == 1 and primary
            garments.append(Garment(
                role=g.get("role", "top"),
                attrs=attrs,
                brand=named[0] if claim else None,
                brand_source="caption" if claim else None,
                notes=body.get("search_phrase"),
            ))

        return Decode(decode_id=did, garments=garments, scene=scene,
                      model=self.p.name, cost_usd=cost, latency_ms=latency)


def to_query(decode: Decode, garment_index: int = 0) -> str:
    """The bridge into retrieval: a decoded garment becomes a search string."""
    g = decode.garments[garment_index]
    parts = [g.value("colour"), g.value("pattern") if g.value("pattern") != "solid" else None,
             g.value("fabric_look"), g.value("silhouette"), g.value("length"), g.value("category")]
    return " ".join(str(p).replace("_", " ") for p in parts if p)

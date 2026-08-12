# twin. — v0 decode engine + eval harness

Phase 0 of the model-independence roadmap. Two days of work, and it's the whole game:
after this exists, "should we use open models?" stops being a debate and becomes a table.

The premise this repo encodes: **decode excellence and catalogue coverage are different
problems, and only one of them is under your control at v0.** Users forgive a thin shelf.
They never forgive being shown trousers when they pasted a dress. So the v0 promise is
"we understand your photo perfectly" — and this repo is how you prove it rather than
assert it.

## Layout

```
vocab.yaml              the definition of done. The editor owns this file.
decode/providers.py     one interface; every model sits behind it
decode/pipeline.py      scene pass -> per-garment reads -> confidences
eval/score.py           the gate: detection, accuracy, calibration
eval/run.py             the provider comparison table
eval/label.py           golden-set labelling CLI (draft-and-correct)
eval/test_*.py          offline tests — no keys, no spend
```

## Run

```bash
python -m eval.test_score      # the scorer is trustworthy
python -m eval.test_pipeline   # the wiring is trustworthy
python -m eval.label --images inbox/ --provider sonnet --labeller editor_01
python -m eval.run --providers sonnet,qwen-vl,llama-v
```

Needs `pyyaml`; `anthropic` / `openai` only for live runs.

## What gets measured, and why three numbers instead of one

A single accuracy figure hides which work fixes the problem.

| metric | what breaks | who fixes it |
|---|---|---|
| **detection F1** | we didn't find the garments | scene prompt, cropping |
| **attribute score** | we found them and misread them | vocabulary, garment prompt, model |
| **calibration gap** | we were confidently wrong | prompt wording |

Calibration is not a nicety. It is the precondition for everything cheap that comes
later — the confidence cascade only works if a small model's "0.9" means 0.9. A model
scoring 0.82 with broken calibration is worse than one scoring 0.78 honestly, because
the cascade cannot route on it.

## The gate

```
attribute_score  >= 0.80
detection_f1     >= 0.85
hard_fail_rate   <= 0.03      category wrong (dress read as trousers)
calibration_gap  <= 0.15      when confidence >= 0.8
```

Nothing ships red. `eval/run.py` exits non-zero when no provider passes, so this drops
into CI unchanged. Tune the thresholds once against the first real run — but tune them
in this file, in a commit, with a reason, not in your head.

## Two design decisions worth defending

**Category is a hard field.** Getting it wrong zeroes the garment rather than costing it
20%. This is deliberately harsh: it makes the one unforgivable product failure impossible
to average away behind good colour scores.

**Near-miss groups give half credit.** Navy read as black under warm light is a different
event from navy read as yellow, and a scorer that treats them identically will send you
chasing the wrong fixes. The `near` groups in `vocab.yaml` are an editorial judgement
about which confusions a stylist would forgive — they belong to the editor, not
engineering.

## Golden set

Target: **300 looks from real saved collections.** Mirror selfies, warm bedroom light,
half-cropped garments, screenshots of screenshots, three people in frame. Clean
e-commerce photography in the golden set will give you a green table and a broken
product.

Slice tags matter more than the headline number. `--only warm_light` and
`--only crowded` are where you find out what's actually wrong; a model can pass overall
while failing every mirror selfie, which is most of your real traffic.

Two integrity rules the labelling tool enforces:
- Every 10th item is served **blind** (no model draft). If pre-filled labels and blind
  labels diverge, your golden set is drifting toward being a copy of the model, and the
  gate is measuring nothing.
- 10% double-labelled for **inter-rater agreement**. A field where two editors disagree
  30% of the time is a vocabulary bug, not a model bug — no prompt work will fix it.

## What this unlocks next

1. **Tagger swap.** The cheapest real win: catalogue tagging is the volume job and
   nobody's brand is harmed if the librarian is 90% as good at a tenth the price. Run the
   table, and if an open model clears the bar on tagging, it replaces Haiku this week
   while frontier keeps the user-facing decode.
2. **The correction ledger.** Every low-confidence attribute becomes a chat
   disambiguation line ("reading this as satin — tell me if I've got the fabric wrong"),
   and every correction becomes a labelled training pair. `decode.weakest()` already
   ranks which attribute to ask about, by weight × uncertainty. From day one, inference
   spend is also dataset spend.
3. **The cascade.** At 10–50K decodes/day this is the difference between ₹25–40K/day and
   ₹2L+/day. Escalation rate — the fraction the small model kicks upstairs — is the
   annexation progress bar.

The failure mode of cheap inference isn't a crash. It's slow, invisible taste-rot that
only a human standard catches. The golden set is that standard, so it has to keep
growing after it stops being fun.

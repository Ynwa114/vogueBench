# Getting this running locally

Nothing here is deployed. This is a folder of files that becomes a working eval
harness in about five minutes. No database, no server, no cloud account.

## 1. Put it somewhere real

Download the `twin_v0` folder, then:

```bash
mkdir -p ~/code && mv ~/Downloads/twin_v0 ~/code/twin-engine
cd ~/code/twin-engine
git init && git add -A && git commit -m "v0 decode engine + eval harness"
```

Commit before you run anything. The point of the harness is that quality changes
are attributable to a diff.

## 2. Setup

```bash
bash setup.sh
```

That creates a venv, installs deps, and runs both test suites. Requires Python 3.10+.
If `python3` isn't found, install it first (`brew install python` on macOS).

Expected output ends with `ALL PASS` twice. If it doesn't, stop and fix that before
anything else — the scorer being correct is load-bearing for every decision downstream.

## 3. Add a key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc     # persist it
```

Only needed for live runs. The tests never call out.

## 4. First real run

```bash
# smoke test on one image before spending anything
mkdir -p inbox && cp ~/Desktop/some-outfit.jpg inbox/
python -m eval.label --images inbox/ --provider sonnet --labeller you
```

That decodes the image, shows you its read, and asks you to correct it. What you're
checking on the first one: does the vocabulary actually cover what you see? If you
find yourself wanting a value that isn't in `vocab.yaml`, that's the vocabulary
telling you it's incomplete — edit it now, before you label 99 more against it.

Then:

```bash
python -m eval.run --providers sonnet
```

With one labelled item the numbers are meaningless. You're verifying the pipeline
runs end to end and produces a table.

## 5. The actual work

100 outfits from **real saved collections** — mirror selfies, warm bedroom light,
half-cropped garments, screenshots of screenshots. Not clean e-commerce photography.
Clean photography gives you a green table and a broken product.

Budget: roughly 2–3 minutes per look once you're in rhythm. Four to five hours total.
Do it in two sittings, not one — labelling fatigue shows up as everything getting
tagged `minimal` around look 60.

Then the run that matters:

```bash
python -m eval.run --providers sonnet,haiku
python -m eval.run --providers sonnet --only mirror_selfie   # where it actually fails
```

## Cost

| | |
|---|---|
| Labelling 100 looks with sonnet drafts | ~$3–5 |
| One full eval run, 100 looks, one provider | ~$3–5 |
| Both test suites | $0 |

Cheap enough to run nightly. That's the point.

## What this is not

No catalog, no retrieval, no API, no app. This is the measurement layer only — the
thing that tells you whether the decode is good enough to build retrieval on top of.
Everything in `twin-infra-decisions.md` comes after this passes.

## Order of operations from here

1. Get this green locally ← you are here
2. Label 100 looks, run the table, pick the tagger
3. Then the ledger (impressions, events, model calls) — the irreversible one
4. Then ingest one retailer end to end
5. Then retrieval
6. iOS only after a curl against the retrieval endpoint returns results you'd ship

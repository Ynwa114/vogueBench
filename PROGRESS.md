# Twin — build progress and collaboration guide

Last updated: 2026-08-12

## Current status

Phase 0, the decode-engine measurement layer, is implemented and its offline safety
gates pass. We have a real-image golden-set seed: three screenshot looks, twelve
labelled garments, spanning mirror selfie, low-light outdoor, warm-light, accessories,
construction detail, and colour ambiguity.

This is **not** a quality result yet. No model has been evaluated on the golden set,
no catalog has been ingested, and no retrieval/API/iOS work has begun. The next honest
number is the first provider evaluation after more real labels exist.

## What has been built

### Decode engine

- `decode/providers.py` exposes one vision-provider interface so model comparisons do
  not require refactoring production logic.
- `decode/pipeline.py` runs scene understanding first, then reads each garment against
  the controlled vocabulary with per-field confidence, caption-only brand evidence,
  model-call logging, and a retrieval query bridge.
- The garment JSON response template is generated from `vocab.yaml`. This prevents a
  field rename from silently making a model emit stale keys.
- `decode/predicates.py` parses deterministic query fragments into three lanes:
  gate, exclude, and rank. Negations become symbolic exclusions rather than vector
  arithmetic. Proposed predicate groundings cannot filter until approved.
- `decode/resolution.py` records per-fragment resolution, cache-hit telemetry, and a
  demand-ranked predicate miss backlog.

### Evaluation harness

- `eval/score.py` separately measures garment detection F1, weighted attribute
  accuracy, category hard failures, and high-confidence calibration.
- `eval/run.py` runs provider comparisons and fails when no provider clears the gate.
- `eval/label.py` supports blind and draft-corrected labelling. It now instructs
  labellers to label occasion and vibe for each garment as a standalone product, not
  copy outfit context onto every garment. Fields scoped away from a category are
  skipped rather than filled with noise.
- `eval/test_schema.py` is the migration safety net. It validates weights, near groups,
  `applies_to`, predicate grounding references, generated decode prompt fields, golden
  labels, and retired identifiers before the other suites run.
- `setup.sh` provisions the local environment and runs schema, scoring, pipeline, and
  predicate suites in that order.

### Current schema: v0.3

`vocab.yaml` is the single human-edited source of truth. The active fields are:

1. category
2. silhouette
3. colour
4. pattern
5. surface_detail
6. fit_ease
7. fabric_look
8. neckline
9. sleeve_length
10. length
11. occasion
12. vibe
13. sheerness

The operational v0 visual schema is twelve structural/filter fields plus the
editor-labelled, rank-only `vibe` layer. The distinction is deliberate: `vibe` is not
a hard gate and must remain editorial, rather than inferred from an embedding.

Notable schema decisions already made:

- `pattern` and `surface_detail` are separate. A garment can be `floral` and
  `sequin`; “nothing sequinned” is now a correct filter.
- Construction detail lives in multi-value `surface_detail`: `ruched`, `ruffle`,
  `pleated`, `bow`, `twist`, and `asymmetric_hem` join applied details such as
  embroidery and zari.
- `fit_ease` is separate from silhouette, pending a real-label redundancy review at
  look 20.
- `sleeve_length` is retained; `sleeve_style` and `rise` are deferred.
- `sheerness` is `opaque | semi_sheer | sheer`, not a boolean.
- `modesty` and garment `coverage` were retired. Constraints use inspectable
  combinations of sheerness, surface detail, category, length, and neckline.
- Garment-only fields are scoped through `applies_to`; bags, belts, footwear, scarves,
  jewellery, sunglasses, hats, and dupattas do not receive invented silhouette,
  fit/ease, length, or sheerness labels.
- The global aesthetic layer is retained. Indian-specific depth belongs in category
  and occasion values, not regional fields.

### Predicate work completed

- `not_too_revealing` now excludes semi-sheer/sheer items, cutouts, explicit revealing
  swim/intimates categories, and a mini-plus-deep-V/strapless combination.
- `nothing_sheer` is grounded solely on the three-level sheerness field. Opaque chiffon
  is not incorrectly removed.
- `not_too_basic` now has construction-detail signals as well as neckline,
  silhouette, fabric look, and ingest-time distinctiveness.
- Predicates are schema-validated so deleted fields and invalid values cannot silently
  lower recall.

## Golden set seed

The reviewed labels live in `eval/golden_set/`:

- `0001_mirror_black_offshoulder.json` — indoor mirror selfie; knit top, trousers,
  belt, bag.
- `0002_orange_ruched_floral_skirt.json` — outdoor/night/warm-light screenshot;
  ruched crop top, floral ruffle skirt, heels, bag.
- `0003_sunset_burgundy_wrap_top.json` — sunset screenshot; wrap top, mini skirt,
  boots, bag.

All are attributed to `ishan` and use garment-intrinsic occasion/vibe labels.

The matching image files are intentionally ignored by Git. Real saved screenshots can
be personal, copyrighted, or otherwise sensitive. Do not push them to a public remote.
Store the team dataset in a private, access-controlled location and copy it locally to
`eval/golden_set/images/` when running a live evaluation. The JSON labels reference
the image filenames and are useful review artefacts, but a live provider run needs the
corresponding local images.

## Verification completed

Run from the repository root:

```bash
source .venv/bin/activate
python -m eval.test_schema
python -m eval.test_score
python -m eval.test_pipeline
python -m eval.test_predicates
```

All four pass as of this update. `bash setup.sh` runs the same sequence.

## What has deliberately not been built

The authoritative build order is being followed. The following are not started:

- provider evaluation on a meaningful golden set;
- model/tagger selection;
- event, impression, and model-call ledger in production storage;
- retailer integration and catalog ingest;
- embedding, design grouping, distinctiveness, trend velocity;
- retrieval endpoint, predicate materialisation worker, watches, notifications;
- iOS screens.

Do not begin iOS work before retrieval returns results worth shipping via `curl`.

## Next milestones

1. Collect and label 100 real saved looks before interpreting model scores. Include
   mirror selfies, warm lighting, screenshots-of-screenshots, crops, crowded images,
   and visible text overlays. At least 10% should be blind labels and 10% should have
   a second labeller.
2. At look 20, review the `silhouette` × `fit_ease` co-occurrence tally. Do not remove
   the field before evidence exists.
3. Configure a provider key and run `python -m eval.run --providers sonnet` as a smoke
   test, then compare candidates only after the set is large enough to diagnose slices.
4. Choose the first retailer only after the remaining user interviews resolve catalog
   priority. This is an explicit open question in `BUILD.md`; do not make it by agent
   inference.
5. Build the production ledger first, then one complete retailer ingest, then live
   retrieval. Follow the build-order table in `BUILD.md`.

## Working with a co-founder

### Repository workflow

1. Create a **private** GitHub repository. The existing local repository has no commits
   and no configured remote, so the initial commit should be made before adding the
   remote.
2. Invite the co-founder with Write access. Enable branch protection on `main` once the
   initial setup is stable: require a pull request, one approval, and passing checks.
3. Use a short-lived branch per change: `codex/<topic>` or `feature/<topic>`. Do not
   develop directly on `main` after the initial commit.
4. Keep `vocab.yaml` and `predicates.yaml` editor-owned. Changes require a small PR
   that states: values changed, predicate impact, re-labelling requirement, and the
   full test result. This prevents vocabulary drift becoming a hidden model-quality
   regression.
5. Treat data separately from code. The private golden-image store should have a
   manifest/version identifier recorded in PRs or evaluation output; do not place
   camera-roll images in Git, issue attachments, public chat, or a public repository.

### Initial GitHub commands

After the initial local commit exists, create an empty private repository in GitHub,
then run (replace the URL):

```bash
git remote add origin git@github.com:YOUR-ORG/YOUR-PRIVATE-REPO.git
git branch -M main
git push -u origin main
```

If the team prefers HTTPS, use the repository HTTPS URL instead. The remote must be
created by an owner with the intended private visibility; that is an external-account
decision and is not assumed by this project.

### Suggested ownership this week

- Ishan / editor: source saved looks, define and review labels, approve vocabulary and
  predicate changes, run user interviews.
- Co-founder / engineering: establish private repo and data access, wire CI for the
  four offline suites, begin ledger/ingest planning only after reading `BUILD.md`.
- Shared: review every schema PR and track the golden-set count, blind-label count,
  double-label count, and slice coverage.

## Rules that should stay visible

- `BUILD.md` is authoritative over older brainstorm documents.
- Do not put the internal codename in user-facing copy, domains, bundle IDs, or store
  listing.
- Never use an LLM as the synchronous retrieval query parser.
- Never relax an exclusion to pad a thin retrieval pool.
- Every model call and every production impression must be logged when production work
  begins.
- No model score is credible until it is based on real saved screenshots rather than
  product photography.

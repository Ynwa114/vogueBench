# Twin — execution runbook

Last updated: 2026-08-14. `BUILD.md` is authoritative; this turns it into a concrete founder checklist.

## Current state

Phase 0 is built: the Python decode engine, vocabulary/predicate layer, labelling CLI,
provider-evaluation runner, and four offline safety suites. All four suites pass.

The reviewed golden set now contains **23 looks** (11 product-page, 12 inspiration)
and their versioned evaluation images. The first live provider comparison is complete:
Sonnet 5 is the only passing provider (attribute score 0.838); Haiku 4.5 and GPT-5.6
Terra miss the hard-fail ceiling only. OpenRouter is the sole live-provider path.

`vibe` is the weakest field across the comparison (Sonnet 0.58, Haiku 0.57,
GPT-5.6 0.69). This is a vocabulary/editorial diagnostic, not permission to tune a
model or change the schema without review. The look-20 co-variance review is closed:
keep both `silhouette` and `fit_ease`; they separate real combinations in the approved
set.

The documented expectation that product pages are easier is currently false:
Sonnet's product-page slice scored 0.782 attribute / 0.833 detection, versus 0.842 /
0.906 on inspiration. This weakens the router assumption in `BUILD.md`; diagnose it
before treating product-page OCR as a cheap path. The next work is the diagnostic pass
on those errors, then the catalog pull—the long pole that has not started. Growing from
23 to 100 looks continues alongside catalog work rather than blocking it.

## Rules that cannot be traded away

- `vocab.yaml` is the one editable source of truth for observable fields/values.
- A missing value is a schema decision, not something a labeller may invent.
- Exclusions are hard constraints; never relax them to pad a thin pool.
- Proposed predicates cannot filter until an editor approves them.
- Do not infer brand from pixels.
- Golden data is real saved/social input, never clean retailer photography.
- Approved golden-set images are versioned with their reviewed labels so evaluation is
  reproducible. Unreviewed source screenshots remain outside Git.
- Do not start iOS until retrieval returns a shelf we would ship via `curl`.

## What is done

| Work | Location | Acceptance proof |
| --- | --- | --- |
| Provider abstraction | `decode/providers.py` | provider calls cannot leak outside adapter |
| Two-pass decode | `decode/pipeline.py` | generated JSON template matches vocab |
| Three-lane predicates | `decode/predicates.py` | symbolic negation and approval guard covered by tests |
| Miss telemetry | `decode/resolution.py` | fragment-level cache/miss reporting exists |
| Quality scorer | `eval/score.py` | detection, attributes, hard failures, calibration separated |
| Labelling CLI | `eval/label.py` | blind and draft-correction paths available |
| Schema guard | `eval/test_schema.py` | fields, groundings, prompt, labels, retired terms checked |
| Golden seed | `eval/golden_set/*.json` | 3 looks / 12 garments, reviewed by Ishan |
| GitHub | `origin/main` | initial commit `9ad5728` pushed to `Ynwa114/vogueBench` |

Run this after every code, schema, predicate, or label change:

```bash
source .venv/bin/activate
python -m eval.test_schema
python -m eval.test_score
python -m eval.test_pipeline
python -m eval.test_predicates
git diff --check
```

## Current schema and settled decisions

Active fields: `category`, `silhouette`, `colour`, `pattern`, `surface_detail`,
`fit_ease`, `fabric_look`, `neckline`, `sleeve_length`, `length`, `occasion`, `vibe`,
`sheerness`.

- The operational v0 schema is twelve structural/filter fields plus editor-labelled,
  rank-only `vibe`. Never turn `vibe` into an auto-derived hard filter.
- `pattern` and `surface_detail` are separate, so floral sequins are representable and
  “nothing sequinned” works.
- `surface_detail` includes applied and construction details: embroidery, sequin,
  beadwork, mirrorwork, zari, lacework, applique, ruching, ruffle, pleats, bow,
  cutout, twist, asymmetric hem, distressing.
- `fit_ease` stays separate from `silhouette`; the look-20 review confirmed useful
  non-redundant combinations.
- `sheerness` is opaque / semi-sheer / sheer. `modesty` and garment `coverage` are
  retired.
- `rise`, `sleeve_style`, coverage, closure, pockets, hemline, stretch, lining, and
  warmth are deferred. They are not to be added casually.
- Scoped fields are omitted for bags, belts, footwear, jewellery, scarves, sunglasses,
  hats, and dupattas. Never use plausible filler attributes for accessories.
- Indian depth belongs in category/occasion values; never create a regional field.

## Golden-set work: Ishan’s primary track

### Goal and slice targets

Reach 100 looks before using model results to select a provider. At look 10, audit the
labelling process; at look 20, review `silhouette` × `fit_ease`; at 50–100, run the
meaningful provider table.

| Slice by look 100 | Minimum | Purpose |
| --- | ---: | --- |
| Mirror selfie | 20 | Core camera-roll behavior |
| Warm/mixed light | 20 | Colour confidence |
| Screenshot/overlay/compression | 20 | Social input quality |
| Partial crop | 15 | Skip rather than guess |
| Crowded/multiple people | 10 | Primary-subject selection |
| Indian wear | 15 | Extension values |
| Accessories present | 20 | Scoped-field behavior |
| Blind labels | 10 | Prevent model-copy labels |
| Double labels | 10 | Reveal vocabulary disagreement |

Slices overlap. Deliberately source the missing slices rather than collecting many
versions of the same clean full-body photo.

### Exact labelling procedure

1. Put one source image in local `inbox/` with a slug: `0021_mirror_green_kurta.png`.
2. First image of every batch is blind:

   ```bash
   python -m eval.label --images inbox/ --blank --labeller ishan
   ```

3. Use provider drafts only when processing volume; correct every field:

   ```bash
   python -m eval.label --images inbox/ --provider sonnet --labeller ishan
   ```

4. Label every shop-worthy garment, including accessories. Ignore other people’s
   garments. Label each garment as if it were alone on its product page; occasion/vibe
   are not copied from the outfit.
5. Use `na` only when a field applies but has no meaningful value. Omit fields outside
   `applies_to`. Add slice tags and a review note for real ambiguities.
6. Run the complete four-suite gate. Record any missing-value issue before changing the
   schema.

### Can the co-founder label too?

**Yes, but as a controlled second editor—not an independent canonical-schema owner.**
This is valuable because editor disagreement is data. Suggested allocation:

- Ishan labels 60 new looks and has final editorial approval.
- Co-founder labels 30 new looks from another source collection.
- Co-founder blind-double-labels 10 selected Ishan looks without seeing Ishan’s JSON.

Use a private shared image store outside Git, with stable matching filenames. Each person
copies needed assets locally to `inbox/` and `eval/golden_set/images/`. Do not push the
images; source rights and personal privacy are unresolved. Commit or PR reviewed labels
only if both founders are comfortable sharing the annotation metadata privately.

At every 10 looks, compare category, warm-light colour, opaque/semi-sheer, scoped-field,
and silhouette/fit-ease disagreements. If two editors materially disagree, stop and
settle the vocabulary/prompt. Do not average the labels.

### Schema-change protocol

Both founders may raise a gap. Neither silently changes `vocab.yaml` or an approved
predicate.

1. Save look ID, garment, intended concept, and why existing values fail.
2. Classify it: alias, new value, predicate, deferred candidate, or true new field.
3. A new field must be pixel-readable, non-derivable, and a hard filter. Regional needs
  almost always become values instead.
4. Review together; Ishan decides canonical editorial meaning.
5. Open one small `schema/<topic>` PR stating changed schema, predicate impact,
   re-labelling impact, and all four test results.
6. Revisit old labels that use the concept, then merge.

## Co-founder’s primary engineering track

The co-founder should spend most build time on this track while contributing the planned
labels. This is the right parallelism: the 100-look bottleneck proceeds, while the
irreversible production foundation is prepared without prematurely building UI or a
speculative retailer scraper.

### A. Repository and CI — do first

1. Clone the private repo and run `bash setup.sh`.
2. Add GitHub Actions that installs Python and runs all four offline suites.
3. Add branch protection to `main`: PR required, one approval, passing CI required.
4. Add a PR template: intent, owner, schema impact, data impact, test output, and
   re-labelling/rollback note.
5. Verify `git status --ignored` shows images remain ignored.

**Done when:** intentionally breaking a grounding or schema value fails CI, and `main`
cannot accept an unreviewed/unverified pull request.

### B. Backend skeleton — do second

1. Read `BUILD.md` sections 5, 8, and 10 before selecting implementation details.
2. Create a TypeScript service skeleton, environment validation, lint/typecheck/test
   commands, migration mechanism, and local development instructions.
3. Configure Supabase/Postgres development and establish auth/RLS conventions.
4. Generate TypeScript vocabulary types from `vocab.yaml`; never hand-maintain enums.
5. Do not build iOS, retrieval, or a public API surface yet.

**Done when:** a fresh clone starts, applies migrations, and typechecks without secrets
in Git or a second manual vocabulary copy.

### C. Ledger — must precede retrieval

Implement and test:

1. User/action `events`.
2. Append-only, monthly-partitioned `impressions(query_pool_id, product_id, position,
   surface, dwell_ms, re_rank_version, pool_seed, ts)`.
3. Model-call records: provider, model version, prompt, raw output, token use, latency,
   cost, and decode/look linkage.
4. Query-pool/rank-version records needed to reproduce a served shelf.
5. Tests proving a request writes the expected trail and impressions are never updated
   or deleted.

**Done when:** each served result/model call is traceable, and the ledger design is
ready before retrieval creates unrecapturable missing data.

### D. Retailer-feed research — parallel, no premature integration

For candidate retailers/feed sources, create a memo covering: allowed access, SKU count,
variant depth, image quality, price/stock cadence, category depth, affiliate click-out,
rate limits, usage terms, and known metadata quality. Prepare a normalised SKU adapter
contract only.

Do **not** select the first retailer until the remaining interviews settle catalog
priority; do **not** build three partial integrations.

**Done when:** there is a decision-ready memo and a documented adapter contract, not a
scraper.

### E. First retailer ingest — only after the retailer decision

1. Ingest raw feed for one retailer.
2. Normalize SKU/variant/stock/price/retailer/source/image metadata.
3. Dedupe while retaining seller copy for audit and brand evidence only.
4. Tag images into the approved schema plus a factual 1–2 sentence description; never
   embed seller copy.
5. Log feed-versus-tagger conflicts, especially category/colour/neckline/sleeve.
6. Embed image and factual description in shared SigLIP space.
7. Add design grouping, distinctiveness, and trend velocity.

**Done when:** sample SKUs have validated attributes, embeddings, conflict logs, design
group IDs, and an idempotent repeatable run.

## Retrieval track — not before first ingest

1. Implement production `QueryState`: gate, exclude, rank.
2. Apply exclusions in SQL before ANN; expand gates only through near groups.
3. Make thin pools relax soft/rank criteria only; exclusions never move.
4. Derive live facets from in-stock pools; select exact/humbler/reach/wildcard slots.
5. Store rank weights as versioned data, not code constants.
6. Add sold-out anchors, design-group variants, and curl tests for `nothing sheer`,
   `not black`, thin pools, sold-out cases, and unresolved fragments.

**Done when:** `curl` produces a small, safe, editorially useful shelf—not just valid
JSON. Only then does iOS begin.

## Provider evaluation — after enough labels

At 1–10 looks, smoke-test the pipeline only. At 50–100 labels, compare providers:

```bash
export OPENROUTER_API_KEY=...
python -m eval.run --providers sonnet --golden eval/golden_set
python -m eval.run --providers sonnet --only mirror_selfie
python -m eval.run --providers sonnet --only warm_light
```

Pass gate: attribute score ≥ 0.80; detection F1 ≥ 0.85; category hard-fail rate ≤
0.03; calibration gap ≤ 0.15. If no model passes, inspect failure slices; never lower
the threshold to manufacture a winner.

## Branch and review process

- `main` remains releasable.
- Use `feature/<topic>` for engineering, `schema/<topic>` for editorial changes, and
  `fix/<topic>` for corrections.
- Do not mix a schema change, a backend migration, and retailer research in one PR.
- Before PR: pull `main`, branch, make one coherent change, run the full gate if schema
  or decode code changed, then push and request review.
- Every PR says: what changed, why, owner, schema/data impact, tests run, and required
  follow-up/re-labelling.

## Immediate tasks this week

| Owner | Task | Done when |
| --- | --- | --- |
| Ishan | Label seven more deliberately diverse looks | Reach 10, all tests green |
| Ishan | Record every missing-value/ambiguity note | Look-10 schema review has evidence |
| Co-founder | Clone and add CI/PR protection | Four suites run on each PR |
| Co-founder | Write retailer-feed feasibility memo | Decision inputs, no integration |
| Co-founder | Start backend skeleton + migration plan | Fresh clone/typecheck/migration path works |
| Both | Choose private image-store workflow | Shared filename/permissions convention exists |
| Both | Review at looks 10 and 20 | Decide schema fixes only with data |

## Friday 2026-08-14 — catalog and golden-set gates

Two tracks run in parallel. The catalog track creates the inventory needed to validate
the tagger prompt; Ishan owns human labels. They meet at one hard gate: do not commit
bulk-tagging spend until the prompt has passed a 50-product catalog-image evaluation.

### Hard rules for the day

- `vocab.yaml` and `predicates.yaml` remain editorial. Report a gap; do not change
  fields or values to unblock work.
- Seller copy and Shopify `body_html` are exact-match, brand-evidence, and audit data
  only. They are never embedded.
- `labelled_by` is always a person. Automated output remains a draft, never golden.
- `impressions` is append-only: no updates or deletes.
- Use only public endpoints; identify the client, rate-limit by domain, respect
  `robots.txt`, and record blocks/404s rather than bypassing them.
- End the day with all four offline suites green.

### Track A — catalog (agent)

1. Build `catalog/stores.yaml` with 40–60 Shopify fashion stores. Every store has a
   domain, `source_tier` (`1` editorially trusted; `2` volume/coverage), and a short
   source note. Verify one store’s `/products.json` response manually before writing
   any loop.
2. Build an idempotent/resumable puller using
   `GET https://{domain}/products.json?limit=250&page={n}` through the first empty
   page. Save raw JSON unmodified and write `catalog/pull_report.json` with domain,
   status, product count, and error. Concurrency is across stores, never within one
   store; rate-limit per domain and use an identifying contact user-agent.
3. Normalise to one row per variant while preserving the Shopify product grouping:
   `sku_id`, `product_id`, `variant_id`, `title`, `vendor`, `product_type`, `tags`,
   `colour_option`, `size_option`, `price`, `currency`, `in_stock`, `image_urls`,
   `primary_image_url`, `source_domain`, `source_tier`, and `body_html_raw`.
   Product grouping is the initial intra-brand design-group signal; do not flatten it
   away.
4. Download and locally cache each primary image at a maximum 512px longest edge before
   any VLM run.
5. Draw a stratified sample of 50 products across Tier 1 brands and product types;
   copy slugged images to `inbox_tagger/`; then stop for Ishan’s tagger-gate labels.
6. Create migrations only (no application surface yet) for `products`, `variants`,
   `embeddings` (`halfvec`, HNSW `m=16`, `ef_construction=64`), append-only monthly
   partitioned `impressions`, `attribute_conflicts`, and `model_calls`.
7. Decide SigLIP hosting—rented GPU or serving provider—and record the decision and
   cost in `catalog/NOTES.md`.
8. After Ishan validates the tagger prompt, submit cheap-tier batch tagging in 10k
   chunks. Each SKU gets schema attributes plus a factual 1–2 sentence description;
   prohibit lifestyle language. Record every feed-versus-tagger discrepancy with
   `pixel_read_wins`.

**Track A done when:** 40+ tiered stores, raw pulls and report exist, real variant count
is known, 512px images are cached, migrations apply, SigLIP hosting is decided, and bulk
tagging is submitted after—not before—the tagger gate.

### Track B — Ishan’s two golden sets

These are deliberately separate distributions and separate gates.

1. **Tagger gate: 50 catalog products.** Label clean Shopify images from
   `inbox_tagger/` into `eval/golden_tagger/`. This tests catalog-image reading and
   gates bulk tagging spend.

   ```bash
   python -m eval.label --images inbox_tagger/ --blank --labeller ishan --market in
   ```

2. **Decode gate: real saved looks.** Keep adding mirror selfies, UI-chrome product
   pages, reels, warm-light images, and partial crops to `eval/golden_set/`. Do not pad
   with clean Pinterest/catalog photography. Current status: 3 approved real looks and
   11 draft records pending human review.
3. At 09:00, ask ten people for twenty saved looks each; this is the slow dependency,
   so start it before other tasks. Draft-correct for volume and label every tenth look
   blind.

   ```bash
   python -m eval.label --images inbox/ --provider sonnet --labeller ishan --market in
   python -m eval.label --images inbox/ --blank --labeller ishan --market in
   ```

4. Target 40–60 reviewed decode looks by day end. Fewer real looks are better than a
   padded but unrepresentative set.

**Track B done when:** 50 person-labelled catalog-product records exist for the tagger
gate, 40+ reviewed real decode looks exist, and no automated draft is misrepresented as
gold.

### End-of-day gate

The day is incomplete unless bulk tagging has been submitted after the 50-product
tagger gate. The rest of the expected evidence is: tiered store list, raw pull/report,
normalised variants, 512px image cache, applied migrations including `impressions`,
40+ reviewed decode looks, and all four suites green.

Do not spend the day on retrieval, web UI, TypeScript application code, accounts,
wishlists, facets, SigLIP embedding runs, or iOS. Those are blocked on the catalog and
the two evaluation gates.

# BUILD.md — twin. v0

**This file is authoritative.** Where it disagrees with any other document in the
repo (`twin-mvp-scope.md`, `twin-backend-spec.md`, `twin-architecture-decisions.md`,
`twin-roadmap*.md`), **this file wins**. Those documents predate later decisions and
contain resolved contradictions. Read them for context, not for instructions.

Codename `twin` is INTERNAL ONLY. `twin.shop` is a live competitor in the same market
and demographic. Do not put the name in user-facing copy, bundle IDs, domains, or the
App Store listing. Use `twin` in code and filenames freely.

---

## 1. What this is

An iOS app for Indian women aged 22–25 who shop online frequently.

**The job.** She sees clothing she wants — usually in an Instagram reel or story —
and the want dies in her camera roll. Today she screenshots it, reverse-image-searches
on Google, and either gives up or forgets. Twin closes the gap between *encountering*
something and *owning or abandoning* it.

**The thesis, in one sentence.** The scarce thing is not visual similarity — Google
Lens already does that well and will stay ahead of us. The scarce thing is
**completeness plus commerce-native reasoning**: every colourway, every print, every
retailer, in stock, priced in rupees, with constraints ("nothing sheer") and degree
("not too basic") that a general image-search structurally cannot express.

**The validated user insight** (from user research, n=1 deep interview, more pending):
her saved items don't convert because of *comparison paralysis from fast-fashion
sameness* — she believes a better colour, print or price exists on a site she hasn't
checked. That is not a search-quality problem. It is a completeness problem, and it is
structurally impossible for any single retailer to solve.

**Competitive position.** The incumbent is **Google Lens**, not Myntra. Myntra and
Meesho have camera search; our user says it is "not very effective". `twin.shop` is a
direct competitor with a curated Shopify-D2C catalog and a search-first (not paste-first)
front door.

---

## 2. What counts as a win

**Primary objective (the ranker optimises this):**

> A win is a screen that produces at least one save the user still has 7 days later,
> weighted by how far that item sits from what she'd have found anyway.

Three properties, all deliberate:
- Unit is the **screen**, not the item. This rewards contrast; pointwise relevance
  punishes it. Ten correct near-identical white tops is a failing screen.
- The **7-day survival** clause kills the sugar-high failure (save in a burst, purge on
  Sunday). 7 days is a guess — instrument the timestamp, pick the real window later
  from data. Do not bake `7` into the metric definition; make it a parameter.
- **Surprise-adjusted** (inverse popularity, or distance from her taste centroid).
  Without this, the cheapest path to saves is showing trending items and the taste
  layer becomes decoration while the numbers rise.

**Company north star:** GMV. **Ranker objective:** durable save rate. The link between
them is an *assumption* — measure it from month one, do not optimise it until volume
makes the measurement meaningful.

**Guardrails that never trade off against the objective:**

| metric | bound |
|---|---|
| decode hard-fail rate (category wrong) | ≤ 3% |
| stated-exclusion violations | 0 (any violation is a P0 bug) |
| unsave / removal rate | tracked as regret signal |
| share of screens returning <10 items | tracked as a HEALTHY number, not a defect |

**Note on the older spec.** `twin-mvp-scope.md` sets `paste→click-out ≥ 25%` as the
success metric. That is superseded. Click-out is still *logged* (it's the revenue
proxy) but it is not what the ranker optimises: it is attribution-lossy, delayed,
inflated by returns, and optimising it early drags the catalog toward cheap impulse SKUs.

---

## 3. What is already built

A Python decode engine + eval harness. **It runs; both offline suites pass; nothing has
been run against real images yet.** All quality numbers in it are targets, not
measurements.

```
twin_v0/
├── vocab.yaml                  # observable attributes. THE definition of done.
├── predicates.yaml             # derived predicates + groundings. 8 entries.
├── decode/
│   ├── providers.py            # one interface; every model sits behind it
│   ├── pipeline.py             # scene pass → per-garment reads → confidences
│   ├── predicates.py           # clause compiler, 3-lane query state, negation
│   └── resolution.py           # per-fragment telemetry + miss backlog
└── eval/
    ├── score.py                # detection F1 / attribute accuracy / calibration
    ├── run.py                  # provider comparison table
    ├── label.py                # golden-set labelling CLI (draft-and-correct)
    ├── baseline.py             # score competitors on our rubric
    ├── queries/twin-fashion-90.yaml   # retrieval benchmark, 57 of 90 written
    ├── golden_set/             # 1 example entry; needs 100
    └── test_*.py               # 3 offline suites, no API keys needed
```

Run `bash setup.sh`. Expect `ALL PASS` three times.

---

## 4. Resolved contradictions

These conflicts exist across the older docs. **Use the RESOLVED column.**

| # | Conflict | Resolved |
|---|---|---|
| 1 | D4 says Voyage multimodal-3; backend spec §3 says SigLIP | **SigLIP.** One shared image+text space. Quality lever is *what* you embed (§7.2), not embedder size — Onton found E5-small at ~98% of E5-base. Voyage stays a challenger in the eval table. Query crops and catalog images MUST share one space or crop-search breaks silently. |
| 2 | `matches` table vs live retrieval | Retrieval is **live**. `matches` is a disposable first-page cache keyed `(look_item_id, tier)` for share pages and re-opens. Deeper pages always computed. |
| 3 | Success metric: click-out vs save | **Durable save rate** (§2). Click-out logged, not optimised. |
| 4 | Tier chips = price bands (`the one/close/smart`) | **Variant axes**: other colours · other prints · cheaper · close alternatives. Price is one axis, not the only one. |
| 5 | D14 serendipity = fixed 1-in-8 random | **Slot roles** assigned before the pool is sliced: the exact one, the humbler one, the reach, the wildcard. |
| 6 | D13 two lanes (correctness / taste) | **Three lanes**: gate (what it is) · exclude (what she'll never wear) · rank (what order). Constraints belong in exclude, never rank. |
| 7 | D12 taste = decayed mean vector | Keep the vector for v0, but the interface is **a prior over predicates**, not a similarity vector. Ship it empty; the shape is what matters. |
| 8 | Camera roll multi-select cap of 4 | **Raise it. Batch import is the first-run flow**, not a chat input option. |
| 9 | Price-drop watch requires wishlisting | **Decoupled.** Anything decoded is watchable. |
| 10 | Feed under chat home | **Cut from v0.** Ship after taste data exists. |

---

## 5. Architecture decisions

Format: decision · why · reversal cost. **ONE-WAY** = treat as permanent for v0.

### 5.1 Data layer

**A1 — Postgres + pgvector on Supabase is the entire data layer. No separate vector DB.**
At 400K SKUs we are 3 orders of magnitude below where a dedicated vector store earns its
operational cost. One DB = one backup story, one auth story, transactional consistency
between attributes and vectors, and filtered-ANN in a single query. Revisit at ~5M SKUs
or filtered-ANN p95 > 300ms. *Reversal: moderate — vectors are re-derivable.*

**A2 — Vectors as `halfvec`, HNSW index** (`m=16, ef_construction=64`, query `ef_search=100`).
768-d float32 × 400K × 2 spaces ≈ 2.5GB raw; HNSW wants 2–3× resident. halfvec halves it
with negligible recall loss and is the difference between a $25 and $100 instance.
Tune `ef_search` from the eval harness, not by feel. *Reversal: trivial — re-index.*

**A3 — pg-boss for queues, not BullMQ+Redis.** Redis still handles session state and rate
limits. Jobs in Postgres = one durability story, transactional enqueue alongside the row
that caused it, no "queue lost a job but the DB says it ran" bugs. *Reversal: low.*

**A4 — Backend is TypeScript** (one service, Next.js for share pages, Supabase, SSE to
iOS). The Python engine is an **offline research tool** and stays Python — it shares
*data* with production (`vocab.yaml`), never *code*. When fine-tuning arrives (Phase 4)
there is no TS path anyway. **Generate TS types from `vocab.yaml` at build time.** The
vocabulary must have exactly one human-edited source of truth; three copies drift
silently and a tagger/retriever disagreement about `midi` produces bad results with no
error anywhere.

### 5.2 Ingest

**A5 — Never embed seller copy. The tagger writes the text we embed. ONE-WAY.**
Pipeline: feed → normalise → dedupe → VLM tagger emits **(a)** the attribute schema and
**(b)** a factual 1–2 sentence physical description with lifestyle language explicitly
forbidden → embed image AND tagger description → upsert. Seller title/description
retained for exact-match evidence, brand extraction and audit only — never similarity.
Onton published hard numbers on this; Indian apparel copy is worse than furniture copy.
*Reversal: HIGH — re-embedding 400K SKUs is a full re-tag. Validate the prompt on 2K
SKUs before the bulk run.*

**A6 — Tagger overrides feed metadata on conflict; log the conflict.**
Indian apparel feeds are unreliable on colour, sleeve, neckline specifically. Write
disagreements to `attribute_conflicts` — free QA data on which retailers and which
fields to distrust. *Reversal: low.*

**A7 — Design-variant clustering at ingest → `design_group_id`.**
Cluster the *same design across colourways, prints and retailers* using
shape/silhouette embedding similarity + attribute agreement on everything except colour
and pattern. This is what makes "every version of this that exists" a single query
instead of a scan. **The completeness promise is not implementable without it.**
*Reversal: moderate — batch job, one column.*

**A8 — Distinctiveness at ingest.** `1 - cosine(product_vec, centroid(category, gender))`,
centroids recomputed nightly. Two consumers: the "not too basic" predicate class, and
the surprise-adjustment in §2. One number, two jobs. *Reversal: trivial.*

**A9 — Trend velocity at ingest.** Rate of new-arrival growth for an attribute cluster
over trailing 30 days, from catalog deltas. Social trend-mining is a dead end (Instagram
hashtags are now a biased corpus of brands and engagement farmers; there is no API for
caption search). **Catalog new-arrivals velocity is the better signal anyway** — it is
what buyers chose to *make more of*, it's India-specific, and it arrives free in the
nightly delta. Used positively for facet freshness and negatively for the
"says I have taste" predicate class. *Reversal: trivial.*

**A10 — Predicate groundings materialised at ingest, never resolved at request time.
ONE-WAY (architecturally).** When an editor approves a grounding, a worker backfills
`product_predicates` across the catalog. A predicate query at request time is then a
boolean column filter. **This is the deliberate divergence from Onton** — they reason
over a graph at query time and pay for it with a custom GPU graph engine we cannot and
should not build. Precompute buys the same behaviour for the price of a nightly job.

**A11 — Facets computed from the live pool, not a static list.** Under-specified queries
("polo shirt") need facet discovery, and facets must reflect what's actually in stock —
no rugby polos this week, no rugby chip. Nightly clustering over `design_group_id`;
**cluster is machine-found, name is human-written.** "Old money" is a predicate, not a
vocabulary value, and naming it that rather than "solid knit polo" is the entire
difference between Twin and a filter sidebar.

### 5.3 Decode

**A12 — Two decode lanes: different models, SLAs, queues. ONE-WAY.**
Forced by batch import. This is the most consequential decision in the doc.

| | Foreground | Backlog |
|---|---|---|
| Trigger | paste, share-sheet, camera | onboarding import, bulk camera roll |
| Model | frontier VLM | cheap tagger tier |
| SLA | p50 < 8s, streams | minutes–hours, notify on completion |
| Cost/image | ₹3–5 | target ₹0.40–0.80 |

At ₹4/image a 40-screenshot import is ₹160/user: fine at 50 users, ₹16L at 10,000
before a single click-out. Nobody watches a backlog decode happen. Backlog items that
later get engagement can be silently re-decoded at frontier quality.

**A13 — Decode is idempotent on perceptual hash.** `decode_cache(phash → look_id)`.
Screenshot backlogs are full of duplicates and reposts. Free money.

**A14 — Source images are private, write-once, never in the feed. ONE-WAY (commitment).**
Batch import means holding hundreds of images per user that were not consciously
uploaded one at a time. Signed URLs, short TTL, owner-only RLS, hard-deleted on account
deletion. Feed and share cards render **catalog imagery only**.

### 5.4 Retrieval

**A15 — Three-lane query state.**
```ts
QueryState = {
  gate:    { category, gender, in_stock, price_window, predicates_required[] },
  exclude: { attributes[], predicates[], design_groups[] },
  rank:    { taste_weight, distinctiveness_floor, slot_roles[] }
}
```
Negations parse into `exclude` and apply as SQL NOT **before** ANN. Never as a vector
nudge — "not beige" embeds *closer* to beige. The `exclude` lane is also what the
"not showing you" chips render from: **the UI and the query state are the same object**,
and dismissing a chip is a mutation of `exclude`.

**A16 — Gates expand across `near` groups; exclusions do not.**
She types "top" colloquially, so a tshirt must survive a "white top" gate — the near
groups in `vocab.yaml` already encode which confusions a stylist forgives. But "not
black" means black, not charcoal. Over-excluding empties the shelf silently and she
never learns why.

**A17 — Pool exhaustion relaxes soft attributes ONLY. ONE-WAY (safety property).**
Relaxation may touch `rank` and soft attributes. It may **never** touch `exclude`.
Padding a thin pool by loosening a modesty exclusion is the worst failure this product
can produce, and it will happen by accident unless explicitly forbidden. **Prefer
returning six items and saying so.**

**A18 — Re-rank weights live in a config table, not code.**
`0.45·visual + 0.35·attribute + 0.10·taste + 0.10·popularity` is a guess. Make it a
versioned row the eval harness can sweep, and stamp the active version onto every served
pool so any historical result is reproducible from the ledger.

**A19 — Never dead-end on sold-out.** Google Lens returns similar items for a sold-out
piece; if we return "unavailable" we are strictly worse than her current tool.
Out-of-stock items render as **anchors** with matches retrieved around them.

### 5.5 Query understanding — three tiers

**A20 — The LLM is never in the retrieval path.**

| tier | mechanism | latency | when |
|---|---|---|---|
| 1 | exact utterance match | <1ms | cached knowledge |
| 2 | nearest utterance in embedding space | ~5ms | paraphrase |
| 3 | LLM proposes grounding, **async** | seconds | true novelty, once ever |

Tier 3 **never blocks**. She gets an honest partial answer immediately plus a visible
chip saying we didn't fully understand that part; the grounding proposal lands in the
editor queue; the *next* woman who phrases it that way hits tier 1.

Two reasons this matters beyond latency: desire decays in seconds, and **a constraint
that resolves non-deterministically is not a constraint** — "not too revealing" must
exclude the same items every time.

Explicitly rejected: an LLM that "understands the query" and emits filters directly.
Same cost every time, unauditable, accumulates nothing.

**A21 — Machine-proposed groundings cannot filter.** `status: proposed` predicates may
only rank, never gate, until an editor signs them. This is the change that makes the
predicate cache an owned asset rather than an LLM guess, and it is where we
*intentionally* differ from Onton's fully-automatic self-learning loop.

### 5.6 The ledger

**A22 — Impressions logged from day one. ONE-WAY. The only genuine point of no return.**
`impressions(query_pool_id, product_id, position, surface, dwell_ms, re_rank_version,
pool_seed, ts)` — append-only, monthly partitions, no updates, no deletes. Separate table
from `events`: the volume profile is 100× different and mixing them makes both slow.

Every item shown-and-ignored is a labelled negative. It is ~95% of the data, it's free,
and **it cannot be recovered retroactively.** ~200–500 impressions/session. At 50 users
≈ 1M rows/month (nothing); at 10K users ≈ 200M/month (partition, then nightly rollup
into `impression_daily` when the first query slows).

**A23 — Every model call logged with prompt, raw output, model version.** Inference spend
is dataset spend; an unlogged call is spend with no residual.

**A24 — Resolution telemetry per query fragment.** Already implemented in
`decode/resolution.py`. Yields (a) cache-hit-rate over time — the flywheel curve, and
(b) **the miss backlog, which IS the predicate work queue, demand-ordered.** You do not
need to mine autocomplete; users rank the backlog for you by frequency.
*Caveat to print on every report: cache hit rate is gameable — a predicate matching
everything raises it and helps nobody. Always read it beside the benchmark class scores.*

### 5.7 Watch & notifications

**A25 — Watch decoupled from wishlist.** `price_watches(user_id, product_id |
design_group_id, target_price, created_from)`. Watching a `design_group_id` is what makes
"it dropped ₹700 *and* it's cheaper in a colour you'll prefer" possible.
Scale: 10K users × 40 backlog items × ~4 matches = 1.6M watches. **Diff catalog-side on
the existing 6h price cron, never poll per-watch.**

**A26 — Notification budget is a system constraint, not a preference.** Max 1 push/user/day,
batched, with a quality floor (min ₹ or % drop), enforced in the worker not the UI. Push
permission is the scarcest asset the app has.

---

## 6. Product spec

### 6.1 Screens (v0 = five; anything not listed is out)

1. **Chat home** — serif greeting, three inputs (camera · camera roll multi-select ·
   paste with clipboard URL auto-detect), three rotating suggestion chips.
   **No feed below.** (Cut per §4.10.)
2. **Result drawer** — bottom sheet, snaps 45% / 92%. Streams: one-line editorial read →
   **editable requirement chips** → variant-axis tier chips → masonry grid.
   **The chat input stays focusable at BOTH snaps.** Refining by typing while the grid
   is open is the fluid-interface moment to protect above everything else.
3. **Item detail** — coupon row, affiliate click-out, watch toggle.
4. **Wardrobe / wishlist** — intent vs want, watch state.
5. **Profile.**

### 6.2 First-run flow (changed — this is the big one)

Not "paste a reel". **"Show me your saves."** Camera-roll multi-select, high cap, batch
import → backlog decode lane → notify on completion.

Why: our user has ~40 screenshots already. Asking her to paste one reel asks her to
start a habit she already has. Batch import breaks the cold-start circularity (feed
quality needs taste data ← needs paste volume ← needs her to return ← needs a good feed)
in one move, and simultaneously produces 40 decodes, 40 watched items, and 40 reasons to
send a notification.

### 6.3 The editable read

Stream the decode as chips in two rows — **"reading this as"** (gate + rank predicates)
and **"not showing you"** (exclusions). Every chip tappable to remove; `+ add` to extend.

One surface, three jobs: it makes honesty states visible, it gives a repair path faster
than retyping, and **every correction is a labelled training pair.** This is the single
highest-value UX element in the product.

### 6.4 Under-specified queries

"polo shirt" returns thousands of equally relevant items. Relevance is worthless here.
Return a small ranked set **plus 4–6 editorially-named facets derived from the live pool**
(rugby stripe · oversized boxy · old money knit · sporty technical · cropped). Picking a
facet mutates the gate. A screen with 24 items and no facets **fails** this class
regardless of relevance.

### 6.5 Cut from v0

Browse feed · outfit assembly for text-first queries (decompose to one garment and let
refinement do the rest — outfit assembly with no taste data produces the uncanny
mannequin look) · in-app checkout · Android (month 2) · the 9-star standing want-list
(ships after price-drop push proves the channel is trusted) · stylist personality
(research showed zero appetite; she wants retrieval, not advice — keep the editorial
serif and the one-line read, cut anything that has opinions about her life).

---

## 7. ML components

| component | model | notes |
|---|---|---|
| Foreground decode | frontier VLM via OpenRouter (start `anthropic/claude-sonnet-5`) | two-pass: scene → per-garment. Per-attribute confidence is load-bearing (drives disambiguation chips, honesty state, cascade routing). |
| Backlog decode | cheap tier, chosen by eval table | quality floor is an open question (§11) |
| Catalog tagger | cheapest model clearing the gate | highest volume, ~$600–900 one-time for 400K SKUs |
| Embeddings | SigLIP, shared image+text space | ~$80 one-time. Small > large (§4.1). |
| Utterance matching | small text embedder | tier 2 only |
| Grounding proposal | frontier LLM, async, once per predicate | output is `status: proposed` |

**Cost reality:** catalog tagging is ~10× the embedding line, not a rounding error next
to it. Foreground decode is the only line that scales linearly with success — which is
why A12 exists and why the confidence cascade is a commercial concern, not an academic one.

**Fine-tuning: not now.** Nothing to train on until the correction ledger accumulates.
When it's worthwhile the target is **the tagger** (highest volume, most repetitive,
degradation recoverable), not query understanding.

---

## 8. Test loops

Three independent gates. They fail for different reasons and get fixed by different work;
collapsing them into one number destroys the diagnostic.

**8.1 Decode gate** (`python -m eval.run`)
```
attribute_score  ≥ 0.80     found them, read them right
detection_f1     ≥ 0.85     found the garments at all
hard_fail_rate   ≤ 0.03     category wrong
calibration_gap  ≤ 0.15     when confidence ≥ 0.8, was it right?
```
Calibration is not a nicety: it is the precondition for the cheap cascade. A model at
0.82 with broken calibration is worse than one at 0.78 that's honest, because you cannot
route on it. Exits non-zero when nothing passes — drop into CI unchanged.

**Golden set: 100 looks from REAL saved collections.** Mirror selfies, warm bedroom
light, half-cropped garments, screenshots of screenshots, three people in frame. Clean
e-commerce photography gives you a green table and a broken product. Slice tags
(`--only mirror_selfie`) matter more than the headline. Integrity rules already enforced
by `label.py`: every 10th item served **blind** (no draft) so the set doesn't drift into
being a copy of the model; 10% double-labelled for inter-rater agreement — a field where
two editors disagree 30% of the time is a **vocabulary bug**, not a model bug.

**8.2 Retrieval gate** (`eval/queries/twin-fashion-90.yaml`)
Per-**screen** scoring, not per-item. Criteria: constraint respected (binary, fatal —
any violation zeroes the screen) · would_save · contrast · completeness.
Classes: under_specified · negation · degree · ungrounded · completeness ·
indian_context · paste · **expected_losses** (published deliberately — size/fit/price
filter queries are marketplace home turf; lose gracefully and hand off).

The `ungrounded` class is scored **twice**: before and after editor approval of the
proposed grounding. **That delta is the flywheel measurement and the single most
important number in the benchmark.**

**8.3 Baseline** (`python -m eval.baseline`)
Same queries, competitors' engines, our rubric. Score **Google Lens first** — it's the
real incumbent. Then `twin.shop`, Myntra, Meesho.
Manual, ~57 queries. Keep it manual: past a certain volume this stops being
benchmarking and becomes a pipeline built on a competitor's product, which teaches you
to imitate their catalog strategy instead of measuring your own.

**8.4 Benchmark hygiene.** The benchmark stays **small and frozen** (57→90 from
interviews, then stop). If it grows weekly you cannot compare months. Predicate seeding
is the opposite job and wants volume — **mine breadth** (autocomplete, forums,
interviews, twin.shop's example prompts), **generate depth** (paraphrases of an
editor-approved predicate). Never generate breadth: that's a model's guess at what
Indian women say.

---

## 9. Edge cases

**Decode**
- Multiple people in frame → primary subject only; ignore garments on others.
- Garment partially cropped / `visibility: barely` → skip rather than guess.
- Screenshot-of-a-screenshot, heavy compression → expect degraded confidence; must not
  produce confident wrong reads.
- Warm indoor light → the classic navy/black and ivory/gold failure. Scene pass emits
  `lighting_risk`; garment pass must drop confidence rather than guess confidently.
- Duplicate images in a backlog import → phash cache (A13).
- Brand named in caption for one garment only ("dress @zara, shoes old") → v0 attributes
  a single named brand to the **primary garment only**. A wrong "this is Zara" is the
  most expensive lie the product can tell. TODO v0.2: caption-span→garment attribution.
- No garments detected → honest empty state, never a fabricated read.

**Query**
- Word-boundary matching is mandatory: `hat` must not match inside "t**hat**", `red` not
  inside "ruched". This bug class produces a plausible wrong gate nobody notices.
- Negation scope ends at comma/`and`/`with`/`;`.
- "not too short" — negation modifying the thing she just asked for.
- Two conflicting contexts ("Goa trip but I'll also meet his parents") → surface the
  conflict, don't silently pick one.
- Query with only a negation ("nothing sheer") → treat as a refinement of the previous
  pool, not a new search.
- Unmatched meaningful fragment → **must be logged as a miss and shown as an
  unresolved chip.** Silently dropping it is worse than failing loudly: the shelf still
  looks plausible and nobody finds out the query was never understood.

**Retrieval**
- Thin pool → return six and say so. Never relax an exclusion (A17).
- Sold out → anchor, don't dead-end (A19).
- All results from one retailer → slot roles should force spread.
- `design_group` with one member → no variant chips; don't render an empty axis.
- Price-drop on an out-of-stock item → suppress the notification.

**Cold start**
- New user, no taste vector → prior is empty, ranking falls back to
  attribute + popularity. Ship the empty prior with the right *interface* (a prior over
  predicates); retrofitting shape later is the expensive version.
- Empty predicate cache → everything is tier 3. Expected. Pre-seed ~15 hand-written
  groundings before first users.

**Trust / safety**
- Modesty groundings are culturally loaded — "not too revealing" differs in Bandra and
  Jaipur. Make the grounding **inspectable** ("why these") and the constraint
  **adjustable and remembered per user**.
- `says I have taste` and similar identity-claim predicates: keep permanently in the
  **rank** lane, `status: proposed`, never gate. If Twin confidently returns a shelf she
  finds tacky, we've told her our taste is worse than hers — unrecoverable for a product
  whose premise is taste.

---

## 10. Build order

**Week 1 is deliberately unglamorous and not negotiable.**

| # | Ticket | Blocks |
|---|---|---|
| 1 | **Ledger**: impressions + events + model-call logging, partitioned (A22, A23) | everything |
| 2 | Wire the 3 offline suites into CI | — |
| 3 | Label 100 golden-set looks; run the eval table; pick the tagger | 4 |
| 4 | Ingest one retailer end-to-end: normalise → dedupe → tag (factual descriptions) → embed (A5, A6) | 5 |
| 5 | `design_group_id` clustering + distinctiveness + trend velocity (A7, A8, A9) | 6 |
| 6 | Retrieval: 3-lane query state, negation as SQL NOT, variant-axis tiers (A15–A18) | 7 |
| 7 | Two decode lanes + batch import flow (A12) | 9 |
| 8 | Predicate tables + editor approval path + materialisation (A10, A21) | — |
| 9 | Watch decoupled + notification worker with budget (A25, A26) | — |
| 10 | iOS: five screens | **all of 1–7** |

**No iOS work until `curl` against the retrieval endpoint returns results you would
ship.** The temptation is strong because the app is the visible part. The drawer is only
as good as what's behind it, and the whole thesis is that the engine is the moat.

Ticket 4 says **one** retailer, not three. One working completely teaches more than
three half-integrated.

---

## 11. Open questions — do not let an agent decide these

1. **Catalog priority order.** Spec assumes marketplace feeds (Cuelinks/Flipkart/Amazon).
   Our one interview named H&M, Zara, Savana, Newme, Slikk. `twin.shop` bet entirely on
   Shopify D2C. **Feed integration is the slowest item on the build path** — needs the
   remaining interviews before ticket 4.
2. **Constraint lane population** — explicit statements only, or inferred from behaviour
   with confirmation? Affects schema and product personality equally. Lean explicit-only
   for v0.
3. **Backlog decode quality floor** — how bad is acceptable for an item nobody is
   watching decode? Determines cheap-tier model choice.
4. **The name.** `twin.shop` is live in this exact market. Nothing user-facing ships
   under it.
5. **`vocab.yaml` is not market-ready.** Four Indian-wear values (saree, kurta, lehenga,
   shrug), no blouse/dupatta/salwar/palazzo/anarkali; `neckline` and `sleeve` are the
   vocabulary of a Zara dress, not a kurta. **`sheer` is referenced by two predicates but
   is not yet a field** — add it before the bulk tagging run. `coverage` needs a tagger
   prompt and a calibration pass. **This is editorial work; a model must not do it.**

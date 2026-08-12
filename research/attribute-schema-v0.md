# Attribute schema research — v0 decision brief

Research date: 2026-08-12. This is a decision input for the editor, **not** an
automatic change to `vocab.yaml`.

## Recommendation

Ship a 14-field visual schema for the first catalog tagging run:

`category`, `silhouette`, `fit_ease`, `colour`, `pattern`, `surface_detail`,
`fabric_look`, `sheerness`, `neckline`, `sleeve_length`, `sleeve_style`,
`length`, `rise`, `occasion`.

Keep `vibe` as an editorial multi-label **rank feature**, not a gate field. It is
valuable product vocabulary, but it fails the hard-filter test. The current field
`sleeve` should be split into length and style. The current `modesty` bucket should
be retired in favour of directly observable `sheerness` plus (later) calibrated
`coverage`; it is too culturally loaded and too coarse for an exclusion.

## Candidate classification

| Attribute | Class | Values, if field | Pixel-readable? | Derivable from | Used as filter? | Footprint / evidence | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| category | FIELD | Global garment taxonomy; India extension below | Yes | — | Yes | Global. Google requires detailed product type; Fashionpedia distinguishes category and attributes; Myntra/Nykaa expose ethnic categories. [Google](https://support.google.com/merchants/answer/7348545) · [Fashionpedia](https://fashionpedia.github.io/home/Fashionpedia_download.html) · [Myntra](https://www.myntra.com/women-anarkali-kurtis-kurtas) | Retain; expand values, not fields. |
| silhouette | FIELD | fitted, straight, A-line, wrap, slip, structured, draped, wide-leg, flared, tapered | Yes | No | Yes | Global. Fashion datasets localise attributes per garment; Myntra exposes top shape and H&M exposes garment style. [Fashionpedia](https://github.com/cvdfoundation/fashionpedia) · [Myntra](https://www.myntra.com/kurta-sets/biba/biba-ethnic-motifs-embroidered-anarkali-sequinned-kurti-with-sharara/24574464/buy) · [H&M](https://www2.hm.com/en_us/productpage.1301271001.html) | Do not use `fit` as a synonym. |
| fit_ease | FIELD | bodycon, slim, regular, relaxed, loose, oversized | Usually | Not reliably | Yes | Global. Nykaa filters Fit; H&M filters Fit and shows loose/oversized/regular/slim. [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=shirts_tops_and_crop_tops_type_filter%3D1772_%3Bfit_filter%3D1599_201_202_5632_%3Bpattern_filter%3D54_%3Bsleeve_length_type_filter%3D1116_11813_11814_%3Bneckline_type_filter%3D1121_1124_1125_1128_1129_1131_1132_1133_1135_1364_1365_1793_&p=2&transaction_id=649ac893a93f0c755a3a3274c588c24c) · [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) | Add; it resolves the existing oversized-boxy ambiguity. Calibrate on model images. |
| colour | FIELD | Current palette; permit up to three colours | Yes | No | Yes | Global across retailer filters and Merchant / Schema.org variant schemas. [Google](https://support.google.com/merchants/answer/7348545) · [Schema.org](https://schema.org/ProductGroup) · [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) | Retain; don't use only `multi` when identifiable colours exist. |
| pattern | FIELD | solid, stripe, check, floral, animal, geometric, paisley, abstract, tie_dye, colour_block, logo | Yes | No | Yes | Global. Google has `pattern`; H&M and Nykaa expose Pattern. [Google](https://support.google.com/merchants/answer/7348545) · [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=shirts_tops_and_crop_tops_type_filter%3D1772_%3Bfit_filter%3D1599_201_202_5632_%3Bpattern_filter%3D54_%3Bsleeve_length_type_filter%3D1116_11813_11814_%3Bneckline_type_filter%3D1121_1124_1125_1128_1129_1131_1132_1133_1135_1364_1365_1793_&p=2&transaction_id=649ac893a93f0c755a3a3274c588c24c) | Retain. Remove `embroidered` and `sequinned`: they are surface treatment, not pattern. |
| surface_detail | FIELD | none, embroidery, sequin, beadwork, mirrorwork, zari, lacework, applique, distressed | Yes for coarse values | No | Yes | India plus global. Nykaa uses Work and pattern/embellished; Fashionpedia models fine-grained local attributes. [Nykaa](https://www.nykaafashion.com/designers/chhavvi-aggarwal/c/8373) · [Fashionpedia](https://github.com/cvdfoundation/fashionpedia) | Add. It makes “no sequins” and “embroidered kurta” correct symbolic filters. Defer fine-grained craft vocabulary. |
| fabric_look | FIELD | cotton, linen, denim, satin, silk, chiffon, jersey, knit, leather, suede, mesh, lace, velvet, corduroy, technical | Yes for visual appearance | No | Yes | Global. H&M filters material; Google / Schema.org converge on material, but actual fibre is feed-only. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jackets-and-coats/jackets.html) · [Google](https://support.google.com/merchants/answer/7348545) · [Schema.org](https://schema.org/ProductGroup) | Retain the `*_look` semantics; never infer composition. |
| sheerness | FIELD | opaque, semi_sheer, sheer | Yes for clear cases | Not safely | Yes | Global. H&M explicitly describes and shoppers review items as sheer; current predicates require it. [H&M](https://www2.hm.com/en_gb/productpage.0904710019.html) | Add before bulk tagging. Its false-negative rate needs a conservative calibration slice. |
| neckline | FIELD | Existing plus mandarin, keyhole, asymmetric; `na` | Yes | No | Yes | Global. H&M and Nykaa expose neckline; relevant Indian products use Mandarin collar. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=shirts_tops_and_crop_tops_type_filter%3D1772_%3Bfit_filter%3D1599_201_202_5632_%3Bpattern_filter%3D54_%3Bsleeve_length_type_filter%3D1116_11813_11814_%3Bneckline_type_filter%3D1121_1124_1125_1128_1129_1131_1132_1133_1135_1364_1365_1793_&p=2&transaction_id=649ac893a93f0c755a3a3274c588c24c) · [Nykaa product](https://www.nykaafashion.com/kaffe-kabeathe-blouse/p/17053365) | Retain, expand. |
| sleeve_length | FIELD | sleeveless, cap, short, elbow, three_quarter, long, extra_long, `na` | Yes | No | Yes | Global. H&M and Nykaa filter / specify it. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=sleeve_length_type_filter%3D1120_1561_20037_2214_29043_&intcmp=nykaa%3Aother%3Anf-tops-store%3Adefault%3Awhats-hot-trending%3ASLIDING_WIDGET_V2%3A8%3Astatement-sleeves%3A-1%3A4322df8ef321cee1d0af6bef3d0c0775&p=28&transaction_id=4322df8ef321cee1d0af6bef3d0c0775) | Rename current `sleeve`; split style below. |
| sleeve_style | FIELD | regular, puff, balloon, bishop, flutter, batwing, raglan, cold_shoulder, strappy | Yes | No | Yes | Global. H&M exposes sleeve style; Nykaa exposes statement sleeve types. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=sleeve_length_type_filter%3D1120_1561_20037_2214_29043_&intcmp=nykaa%3Aother%3Anf-tops-store%3Adefault%3Awhats-hot-trending%3ASLIDING_WIDGET_V2%3A8%3Astatement-sleeves%3A-1%3A4322df8ef321cee1d0af6bef3d0c0775&p=28&transaction_id=4322df8ef321cee1d0af6bef3d0c0775) | Add; current field joins two independently-filtered dimensions. |
| length | FIELD | cropped, waist, hip, tunic, mini, midi, maxi, ankle, full, `na` | Yes | No | Yes | Global. H&M filters length; Indian listings expose top length. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Myntra](https://www.myntra.com/kurta-sets/biba/biba-ethnic-motifs-embroidered-anarkali-sequinned-kurti-with-sharara/24574464/buy) | Retain; make category-specific labels explicit in prompt. |
| rise | FIELD | low, mid, high, `na` | Usually | No | Yes | India + global. Nykaa exposes Rise even on designer/ethnic catalog pages. [Nykaa](https://www.nykaafashion.com/designers/sainy-garg/c/64457?ptype=listing%2Cbrands%2Csearch%2Csainy-garg-couture&root=nav_3) | Add only for bottom categories. Validate its real-image accuracy before rollout. |
| occasion | FIELD | Global core + regional values below | Sometimes | No | Yes | Global. H&M and Nykaa filter occasion; iMaterialist includes occasion categories. [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) · [Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=shirts_tops_and_crop_tops_type_filter%3D1772_%3Bfit_filter%3D1599_201_202_5632_%3Bpattern_filter%3D54_%3Bsleeve_length_type_filter%3D1116_11813_11814_%3Bneckline_type_filter%3D1121_1124_1125_1128_1129_1131_1132_1133_1135_1364_1365_1793_&p=2&transaction_id=649ac893a93f0c755a3a3274c588c24c) · [iMaterialist](https://arxiv.org/abs/1906.05750) | Retain multi-label; confidence must be lower than structural fields. |
| vibe | PREDICATE / rank feature | — | Partly | structure + surface + embeddings | Usually no | Aesthetic terms are spoken language, but published style labels are inconsistent. [DeepFashion assessment](https://www.mdpi.com/2076-3417/12/19/10062) | Preserve existing editorial taxonomy but do not gate with it. |
| modesty | PREDICATE | — | No, as a stable cultural judgement | sheerness + coverage + neckline + length | Yes, but inspectable | The current predicate already needs component attributes. | Replace the coarse bucket; make user-adjustable. |
| coverage | DEFER | 0–1 derived score | Not yet at required accuracy | segmentation / length / neckline | Yes | Needed by current predicates but not evidenced as a reliable photo-only field. | Build a calibration set before adding. |
| fabric fibre / composition | DROP | — | No | feed metadata | Yes | Google requires material in feeds, but H&M composition demonstrates it is factual metadata rather than reliable pixels. [Google](https://support.google.com/merchants/answer/7348545) · [H&M](https://www2.hm.com/en_us/productpage.1295399001.html) | Store seller feed separately; never vision-tag. |
| size / size system | DROP | — | No | seller variant metadata | Yes | Google requires it for commerce, not image retrieval. [Google](https://support.google.com/merchants/answer/7348545) | Product variant field, outside visual schema. |
| gender / age group | DROP | — | No / inappropriate inference | catalog metadata | Yes | Merchant attributes target intended customer, not garment pixels. [Google](https://support.google.com/merchants/answer/6324479?hl=en-GB) | Use explicit catalog metadata only. |
| brand | DROP | — | No except explicit OCR | feed / caption evidence | Yes | A wrong visual brand claim is explicitly prohibited by the build spec. | Existing decode handling is correct. |
| quality / durability / won't crease | PREDICATE | — | No | fabric_look + feed care metadata | Yes | H&M and retailers expose care/composition, not a photo-verifiable quality field. [H&M](https://www2.hm.com/en_us/productpage.1295399001.html) | Feed-backed predicate, never a vision attribute. |
| expensive-looking / old money / clean girl / y2k | PREDICATE | — | Partly | visual fields + embeddings + editorial rules | Rank only | Style taxonomies are inconsistent; DeepFashion research warns style categories are hard to define. [DeepFashion assessment](https://www.mdpi.com/2076-3417/12/19/10062) | Global aesthetic layer, never regionalised. |
| office appropriate / wedding guest / date night | PREDICATE | — | No, context-dependent | occasion + coverage + surface_detail + vibe | Yes | Current grounding file correctly marks several as proposed. | Keep human approval before gates. |
| closure / pocket / hemline | DEFER | — | Yes | partly category-dependent | Sometimes | Retailers expose them, but no evidence they are primary v0 hard filters. [Nykaa](https://www.nykaafashion.com/kaffe-kabillie-shirt/p/17053405) · [H&M](https://www2.hm.com/en_us/productpage.1322471002.html) | Add only when miss backlog demands it. |
| body shape / flattering | DROP | — | No | subjective and user-specific | Often spoken, not safely filterable | No stable global taxonomy. | Do not encode body judgements. |

## Regional extension: values, not parallel fields

India category values to add: `kurti`, `kurta_set`, `anarkali`, `blouse`,
`dupatta`, `salwar`, `churidar`, `palazzo`, `sharara`, `gharara`, `ethnic_skirt`,
`pre_draped_saree`, `drape_saree`, `pant_saree`, `indo_western_set`.

Retailers are inconsistent: Myntra uses both *kurta* and *kurti* and makes
`anarkali` a kurta subtype; listings combine `kurta with palazzo and dupatta`, while
Nykaa separately names `kurti`, `sharara`, `palazzo`, and several pre-draped saree
forms. The editor should select canonical values and preserve the alternatives as
search aliases, not duplicate categories. [Myntra](https://www.myntra.com/anarkali) ·
[Myntra product](https://www.myntra.com/kurta-sets/biba/biba-ethnic-motifs-embroidered-anarkali-sequinned-kurti-with-sharara/24574464/buy) ·
[Nykaa](https://www.nykaafashion.com/designers/chhavvi-aggarwal/c/8373).

India occasion additions: `haldi`, `mehendi`, `sangeet`, `wedding_ceremony`,
`reception`, `festive_puja`, `eid`, `diwali`, `navratri_garba`. Keep the global core:
`everyday`, `work`, `brunch`, `date`, `party`, `night_out`, `wedding_guest`,
`vacation`, `resort`, `lounge`, `gym`, `travel`, `formal`. Festival editorial pages
make clear that Indian events have differentiated dress norms rather than a generic
party bucket. [Nykaa Durga Puja edit](https://www.nykaafashion.com/style-files/howtoblog/durga-puja-edit-celebrate-the-warrior-goddess-with-style).

Later regional category additions follow the same pattern: `abaya`, `kaftan` (Gulf),
`kebaya` (SEA), and hanbok-derived categories (Korea). None is evidence for a new
regional field.

## Convergent attributes

The strongest cross-source fields are category/product type, colour, pattern,
material appearance, size (commerce metadata only), fit, neckline, sleeve length,
length, and occasion. Google / Schema.org converge on variant-defining colour,
material, and size; H&M has live global filtering for pattern, neckline, sleeve,
length, fit, occasion and material; Nykaa exposes the same structural facets plus
India-specific work and rise. [Google](https://support.google.com/merchants/answer/7348545) ·
[Schema.org](https://schema.org/ProductGroup) · [H&M](https://www2.hm.com/content/hmonline/en_gb/ladies/shop-by-product/jumpsuits/long-jumpsuits.html) ·
[Nykaa](https://www.nykaafashion.com/women/westernwear/tops/c/4497?f=shirts_tops_and_crop_tops_type_filter%3D1772_%3Bfit_filter%3D1599_201_202_5632_%3Bpattern_filter%3D54_%3Bsleeve_length_type_filter%3D1116_11813_11814_%3Bneckline_type_filter%3D1121_1124_1125_1128_1129_1131_1132_1133_1135_1364_1365_1793_&p=2&transaction_id=649ac893a93f0c755a3a3274c588c24c).

## Contested attributes and deferrals

- `silhouette` versus `fit_ease`: retain both. Silhouette describes the cut
  (boxy, A-line, wide-leg); fit/ease describes volume on the body (slim, regular,
  oversized). H&M and Nykaa distinguish Fit from other garment attributes, and the
  product requirement names an actual failure from conflating them.
- `sleeve`: split `sleeve_length` from `sleeve_style`; both are independently
  filtered by H&M, and statement sleeves matter for search.
- `pattern` versus `surface_detail`: split now. A sequinned floral garment needs
  `pattern=floral` and `surface_detail=sequin`; combining them makes `no sequins`
  impossible without incorrectly excluding all embroidery-like patterns.
- Defer `coverage`, closure, pockets, hemline, care, stretch, lining, warmth,
  sustainability and craft-specific work types. They need either calibration or
  demand evidence before a 400K-SKU re-tag.

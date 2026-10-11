# The five-stage pipeline in detail

The design goal: each stage does the thing it is good at, and no stage invents
information. The LLM contributes *reasoning over context*; the gazetteer
contributes *geographic ground truth*; the uncertainty model contributes
*honesty about resolution*.

---

## Stage 1 — Recognize (geoparsing / toponym recognition)

Find the spans of text that denote places, and keep enough around them to
resolve later.

Options, roughly increasing in cost and capability:
- **Rule/NER models**: spaCy `GPE`/`LOC`/`FAC` entities, or a dedicated
  geoparser (Mordecai3, the Edinburgh Geoparser). Fast, cheap, misses relative
  descriptions and messy phrasing.
- **LLM extraction**: prompt the model to return every place mention *and* every
  spatial expression, including relative ones ("just south of", "the
  border region"). This is where an LLM adds value over classic NER, because
  "20 km upriver from the dam" is a location that NER will not tag as one entity.

For each mention keep: the **verbatim string**, its **character offset**, and a
**context window** (the sentence, plus the dateline and headline). Offsets let
you dedupe repeated mentions and trace results back to the text.

Do **not** resolve or geocode here. Recognition only.

---

## Stage 2 — Resolve (toponym resolution + typing + relevance)

The heart of the method, and the part LLMs do well. For each mention, using the
whole document as context, produce:

1. **Unambiguous reference string** — a fully qualified name a gazetteer can
   match: `Springfield, Illinois, United States`, not `Springfield`. Include
   admin hierarchy the text implies even if not adjacent to the mention (the
   dateline said Illinois twelve lines up).
2. **Feature type** — populated place / admin unit (which level) / POI or
   facility / water body / natural feature / relative-offset / region. Drives the
   default uncertainty and the lookup strategy.
3. **Relevance role** — is this the story's *event* location, the *reporting*
   location (dateline), or an *incidental* mention (a comparison, an official's
   hometown, an org headquartered elsewhere)? See `news_specifics.md`.
4. For relative descriptions, a **structured offset**: anchor name + distance +
   bearing (or "near"/"outskirts" as a fuzzy offset).

Prompt template: `resolution_prompt.md`. Ask for structured JSON, one object per
mention, and forbid coordinates in the output — the model must not emit lat/lon
even if it "knows" them.

Disambiguation policy, in order:
1. Explicit context in the text (an adjacent or dateline admin unit, a country
   named nearby, a river or landmark that co-occurs).
2. Coreference across the document (the same bare name later qualified).
3. Real-world salience **only as a last-resort tiebreaker** (capital, largest
   city, largest population). Record when you fell back to this in remarks —
   it is the main source of silent error.

---

## Stage 3 — Look up (gazetteer)

Send the **reference string**, not the bare mention, to the geocoder. Retrieve:
center coordinates, the matched feature's **bounding box / extent**, its feature
class, and the matched name (to verify you got what you asked for — a Nominatim
result whose type is `administrative` when you wanted a POI is a red flag).

Geocoder notes:

- **Nominatim (OSM)** — `https://nominatim.openstreetmap.org/search`. Returns
  `boundingbox`, `class`, `type`, `importance`. Public server: **max 1
  request/second**, requires a real `User-Agent`, no heavy batch. Self-host
  (Docker) for corpora. Best street/POI coverage.
- **GeoNames** — `http://api.geonames.org/searchJSON`. Needs a free `username`.
  Returns `fcl`/`fcode` (feature class/code), `population`, admin hierarchy
  (`adminName1`...), and `bbox` for many features. Excellent for populated-place
  disambiguation and for population-as-tiebreaker.
- **ArcGIS World Geocoder / Google / Mapbox(Pelias)** — commercial, high
  throughput, strong address parsing. Watch result-storage/caching terms in the
  license before persisting coordinates.

Robustness:
- **Cache** every query (string -> raw response) on disk. Re-running a corpus
  should hit the network zero times for repeats. `geocode.py` does this.
- **Retry** with a slight backoff on transient failures; obey rate limits.
- Cross-check with a **second geocoder** when precision matters; large
  disagreement between two providers is a strong "review this" signal.
- If nothing matches, try progressively coarser reference strings (drop the POI,
  keep city; drop city, keep admin unit) and *widen the uncertainty
  accordingly*, rather than failing outright — but record how far you backed off.

---

## Stage 4 — Assign uncertainty (point-radius)

Turn the match into a `coordinateUncertaintyInMeters`. Priority of sources:

1. **Gazetteer extent** — if you have a bounding box, the radius is the distance
   from the center to the corner (half the diagonal). This is the most defensible
   value because it is derived from the actual feature, not a guess.
2. **Feature-type default** — no bbox (a bare point): use the typed default from
   the radius table in `uncertainty.md`.
3. **Computed geometry** — for relative offsets, propagate anchor uncertainty +
   distance/bearing imprecision (see `uncertainty.md`, "distance at a heading").

Never 0, never null. A GPS-grade coordinate lifted verbatim from a story still
carries the source's own error; a country centroid carries hundreds of km.

---

## Stage 5 — Emit (Darwin Core record)

One record per resolved location. Core fields (full list in `uncertainty.md`):
`decimalLatitude`, `decimalLongitude`, `geodeticDatum` (WGS84),
`coordinateUncertaintyInMeters`, `verbatimLocality` (the mention),
`locality` (resolved reference string), `georeferenceSources` (which gazetteer),
`georeferenceProtocol` ("point-radius; Chapman & Wieczorek 2020"),
`georeferenceRemarks` (disambiguation reasoning, fallbacks, relevance role),
and your own `relevanceRole` / `featureType` extension columns.

Keeping the verbatim string and the remarks is what makes the output auditable
and lets a human spot-check the machine's decisions later.

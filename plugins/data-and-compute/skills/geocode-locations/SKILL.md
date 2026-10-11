---
name: geocode-locations
description: "Assign coordinates and calibrated uncertainty to places described in words, in any text: field notes, museum and specimen labels, survey sheets, papers and reports, news stories, interview transcripts. Use whenever a task turns locality descriptions into latitude and longitude: resolving ambiguous place names (\"Paris\" -> which one), grounding relative descriptions (\"20 km north of Goma\", \"off the coast of Sicily\"), batch-georeferencing a set of records, or producing point-radius / Darwin Core georeferences with coordinateUncertaintyInMeters; also to review a geocoding pipeline. Core rule: the language model disambiguates the name, a gazetteer supplies the coordinates."
---
# Geocoding described locations

## What this skill is for

Two jobs, often together:

1. **Build/run** a geocoding pipeline that reads free text (field notes, a
   specimen label, a survey sheet, a paper, a news story) and returns, for each place worth locating, a
   center coordinate plus a calibrated uncertainty radius and enough provenance
   to defend it later.
2. **Audit** an existing geocoder against the *method*. The most common failure
   is asking an LLM for latitude/longitude directly. Name it and fix it.

Default to writing code the user runs, unless asked to execute it. Match their
stack; do not adopt a convention that is methodologically wrong because existing
code uses it.

## The one rule that matters most

**The language model resolves the name. The gazetteer supplies the
coordinates.** LLMs are strong at the hard part of this problem (using article
context to decide that "Paris" means Paris, Texas, or that "the capital" refers
to a country named three sentences earlier), and unreliable at the easy-looking
part (emitting a precise lat/lon), where they interpolate plausible but wrong
numbers. Current toponym-resolution research (Hu et al. 2024; and follow-ups
through 2026) converges on exactly this split: fine-tuned or prompted LLMs
estimate an *unambiguous reference string* such as `Paris, Texas, United States`,
then Nominatim / GeoNames / ArcGIS turn that string into coordinates. Never let
a coordinate originate from the model's own weights. If the pipeline can't get a
gazetteer hit, it returns "unresolved," not a guess.

## Why the museum method applies here

Natural-history collections have georeferenced textual locality descriptions for
decades. That community solved problems reportage shares: vague places, relative
offsets ("5 mi S of town"), features rather than points, and the need to record
*how sure* you are. The transferable core is the **point-radius method**
(Wieczorek et al. 2004; GBIF Best Practices, Chapman & Wieczorek 2020): every
location is a center point **plus a radius** capturing the largest plausible
distance the true location could be from that point. A country, a city, and a
street corner are all valid georeferences; they differ by radius, not by whether
they "count." Output in **Darwin Core** terms so the result is interoperable and
auditable. See `references/uncertainty.md`.

Narrative text (news stories, reports, interviews) differs from specimen labels
in three ways the pipeline must handle explicitly, covered in
`references/news_specifics.md`:
- Multiple places per document, only some of which are the *story's* location.
- Dateline / place-of-reporting vs. place-of-event (often different cities).
- Event footprints that are areas, routes, or regions, not points.

## The pipeline

Read `references/pipeline.md` for the full version. In brief, five stages:

1. **Recognize** toponyms and spatial expressions in the text (NER / LLM
   extraction), keeping each mention's surrounding context and character offset.
2. **Resolve** each mention to an unambiguous reference string **and a feature
   type** (populated place, admin unit, POI, water body, relative offset, ...),
   using the LLM with the article as context. Prompt template in
   `references/resolution_prompt.md`. This stage also decides *relevance* (is
   this the story's location or an incidental mention?).
3. **Look up** the reference string in a gazetteer to get center coordinates,
   the matched feature's extent/bounding box, and its own feature class.
4. **Assign uncertainty**: convert the gazetteer extent (or a feature-type
   default, or the geometry of a relative offset) into
   `coordinateUncertaintyInMeters` via the point-radius model.
5. **Emit** a Darwin Core-style record per location with center, radius, verbatim
   text, resolved name, source, and remarks. Keep the verbatim string always.

`scripts/geocode.py` is a runnable reference implementation of stages 3-5
(gazetteer lookup + uncertainty + Darwin Core output) with on-disk caching and
graceful "unresolved" handling. It is deliberately geocoder-agnostic.

## Relative and complex descriptions

"20 km north of Goma" is not a gazetteer entry. Resolve the anchor ("Goma"),
geocode *that*, then apply the offset (bearing + distance) to compute the center,
and propagate both the anchor's uncertainty and the offset's imprecision into the
radius. This is the museum "distance at a heading" locality type. The math and
uncertainty combination live in `references/uncertainty.md`; `scripts/geocode.py`
implements `offset_point()`.

## Non-negotiables (audit checklist)

- [ ] No coordinate ever comes from the LLM. Gazetteer or computed-from-anchor
      only. A pipeline that prompts "give me the lat/lon of X" is broken.
- [ ] Every record carries a **radius** (`coordinateUncertaintyInMeters`). A
      point with no uncertainty is not a georeference. Uncertainty is never 0.
- [ ] The **verbatim** text and the **resolved** reference string are both
      retained. You must be able to see what the machine read and what it decided.
- [ ] Ambiguous names are resolved from **document context**, not by blindly
      taking the gazetteer's highest-population match. (Population is a
      reasonable *tiebreaker of last resort*, not the resolver.)
- [ ] Country / admin-unit mentions get **centroid + large radius**, not a
      falsely precise point. Don't drop them for being coarse.
- [ ] Relevance is separated from resolvability: a correctly resolved but
      incidental place should be flagged, not silently mixed with the story's
      location.
- [ ] Datum recorded (`geodeticDatum`, effectively always WGS84 / EPSG:4326 for
      web gazetteers). Coordinates in decimal degrees, W and S negative.
- [ ] Failures return an explicit unresolved record with a reason, never a
      fabricated coordinate or a silent drop.

## Gazetteer choice (stage 3)

Match the user's constraints; don't hard-code one. Quick orientation, full
notes in `references/pipeline.md`:
- **Nominatim / OpenStreetMap** — free, forward + reverse, strong on
  streets/POIs, returns bounding boxes (useful for radius). Respect the 1 req/s
  public-server limit or self-host for batch.
- **GeoNames** — 25M+ names, populated places and admin hierarchy, population and
  feature class per record, good for disambiguation. Free tier needs a username.
- **ArcGIS / Esri, Google, Pelias/Mapbox** — commercial, higher throughput and
  address quality, licensing constraints on storing results.
- Combining two and cross-checking agreement is a well-supported way to catch
  bad matches.

## Scope and honesty

Coarse but correct beats precise but wrong. A story about "flooding across
Bangladesh" is a country-sized georeference, and that is the right answer, not a
failure. When context genuinely underdetermines the place, say unresolved.

# What makes news different from specimen labels

A specimen label describes *one* collecting locality. A news story mentions many
places, most of which are not where the story happened. Handling this is the
difference between a geocoder that "found 11 locations" and one that found *the*
location. Three issues:

## 1. Many places, one (or few) that matter — relevance

Separate **resolvability** (can I put a coordinate on this name?) from
**relevance** (is this the story's location?). A place can be perfectly resolved
and completely incidental. Tag each mention with a role:

- **event** — where the reported thing actually happened. Usually what you want.
- **dateline / reporting** — where the story was filed (often a bureau city like
  London or Washington), frequently *not* where the event occurred.
- **incidental** — comparisons ("larger than Belgium"), an official's hometown,
  an organization's headquarters, historical references, "experts at Stanford
  said". Resolvable, rarely relevant.

Do the tagging in the resolution stage with the LLM, which can read intent from
context. Keep incidental places in the output but flagged, so a downstream user
can filter rather than having them silently dropped or silently promoted.

For many analyses you want a small number of **focus locations** per story, not
every GPE token. Let the consumer decide the threshold; your job is to label
honestly.

## 2. Dateline vs. event location

The dateline (the "GOMA, Congo —" at the top, or the byline city) is where the
story was *reported*, which may differ from where the event was. Treat the
dateline as strong context for resolving *bare* later mentions ("the city",
"the region") but do not assume the dateline is the event location. When the
event location is stated, it wins; when only the dateline exists, mark the
story's location as dateline-derived in remarks.

## 3. Events are often not points

A specimen came from a point. News events are frequently:

- **Areas** — "flooding across Bangladesh", "wildfires in Los Angeles County".
  The correct georeference is the admin unit's centroid with an admin-sized
  radius. This is a *correct coarse answer*, not a failure. Do not try to fake a
  precise point.
- **Routes / lines** — "along the M4 corridor", "the Lewis and Clark route".
  A single point badly misrepresents these. Either pick a representative center
  with a radius spanning the route, or (better, if the consumer supports it)
  store a `footprintWKT` line/polygon alongside the point-radius.
- **Multiple sites** — "attacks in three cities". Emit one record per site;
  don't average them into a meaningless midpoint in the sea.

When an event genuinely spans a region, the region *is* the answer. Coarse but
correct.

## Other reportage quirks

- **Metonymy**: "Washington announced", "Beijing denied", "Downing Street said"
  refer to governments, not the spot. Resolve to the seat-of-government point
  only if a location is actually wanted, and flag it — often these should be
  incidental.
- **Bare re-mentions**: "the city", "the town", "there" resolve by coreference
  to an earlier named place. The LLM handles this from context; a pure gazetteer
  cannot.
- **Historical / fictional / renamed places**: note when a name is historical
  (Constantinople), contested, or renamed; geocode to the intended referent and
  record the reasoning.
- **Homograph traps**: "Reading" (place vs. verb), "Of" villages, "Nice" — the
  recognizer will over- and under-fire. Context resolution and a
  gazetteer-type sanity check catch most.
- **Non-English and transliteration**: the same place appears under multiple
  romanizations; the resolved reference string should use the gazetteer's
  canonical form so lookups are stable.

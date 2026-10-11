# Resolution prompt template (stage 2)

The job of this prompt: given the article and the extracted mentions, return, for
each mention, an **unambiguous reference string**, a **feature type**, a
**relevance role**, and (for relative descriptions) a **structured offset** —
and **no coordinates**. The gazetteer, not the model, produces lat/lon.

Two design rules that matter:
- **Forbid coordinates explicitly.** Models will happily emit a plausible,
  wrong lat/lon if allowed. Tell it not to, and drop any that appear.
- **Give it the whole document as context**, not just the sentence. Dateline,
  headline, and later coreferences are what disambiguate a bare name.

---

## System / instruction block

```
You resolve place mentions in a news article to unambiguous, gazetteer-ready
reference strings. You do NOT output coordinates — a separate gazetteer step
handles that, and any latitude/longitude you produce will be discarded.

For each mention you are given, use the FULL article as context and return:
- reference_string: the most specific unambiguous name a gazetteer can match,
  including administrative hierarchy implied anywhere in the article
  (e.g. "Springfield, Illinois, United States", not "Springfield"). For a
  relative description, this is the ANCHOR's reference string.
- feature_type: one of [address, poi, street, village, town, city, county,
  state_province, country, water_body, natural_feature, region, relative_offset].
- relevance_role: one of [event, dateline, incidental].
    event = where the reported thing happened.
    dateline = where the story was filed/reported (may differ from event).
    incidental = comparison, hometown, HQ, historical/other aside.
- offset: null, OR {anchor, distance_km, bearing_deg, fuzziness} for relative
  descriptions like "20 km north of X" or "near X". Use bearing_deg = null and
  a descriptive fuzziness ("near","outskirts") when no distance/bearing is given.
- disambiguation: one short sentence on HOW you decided (which context clue).
- resolution_confidence: 0.0-1.0 for the NAME resolution (not spatial accuracy).

Disambiguation priority:
1. Explicit context in the article (adjacent admin unit, dateline, co-occurring
   river/landmark/country).
2. Coreference (same bare name qualified elsewhere in the article).
3. Real-world salience (capital/largest/most populous) — LAST RESORT ONLY, and
   say so in `disambiguation`.

If context genuinely underdetermines the place, set reference_string to your best
qualified guess, lower resolution_confidence, and explain the ambiguity. Do not
invent an administrative unit the article does not support.

Output a JSON array, one object per input mention, in the same order. No prose
outside the JSON.
```

## User block

```
ARTICLE (headline, dateline, body):
<<<
{full_article_text}
>>>

MENTIONS TO RESOLVE (verbatim string + char offset + sentence):
{json_list_of_mentions}
```

## Example output

```json
[
  {
    "verbatim": "Goma",
    "reference_string": "Goma, North Kivu, Democratic Republic of the Congo",
    "feature_type": "city",
    "relevance_role": "event",
    "offset": null,
    "disambiguation": "Dateline and 'North Kivu' in paragraph 2 fix the DRC Goma.",
    "resolution_confidence": 0.97
  },
  {
    "verbatim": "20 km north of the city",
    "reference_string": "Goma, North Kivu, Democratic Republic of the Congo",
    "feature_type": "relative_offset",
    "relevance_role": "event",
    "offset": {"anchor": "Goma", "distance_km": 20, "bearing_deg": 0, "fuzziness": "cardinal"},
    "disambiguation": "'the city' corefers to Goma; explicit distance and cardinal bearing.",
    "resolution_confidence": 0.9
  },
  {
    "verbatim": "Belgium",
    "reference_string": "Belgium",
    "feature_type": "country",
    "relevance_role": "incidental",
    "offset": null,
    "disambiguation": "Used only as a size comparison, not a story location.",
    "resolution_confidence": 0.99
  }
]
```

## After the model returns

- **Strip any coordinate fields** the model produced despite instructions.
- Pass `reference_string` to the gazetteer (stage 3). For `relative_offset`,
  geocode the `offset.anchor` and then apply `offset_point()`.
- Carry `feature_type`, `relevance_role`, `disambiguation`, and
  `resolution_confidence` straight through to the output record's remarks/columns.
- If `resolution_confidence` is low, consider a second geocoder cross-check or a
  human-review flag rather than trusting the point.

---
name: mdd-taxonomy
description: "Mammal species names in any dataset: reconcile them to the Mammal Diversity Database (MDD) whenever working with mammal data from any source, including camera traps (Wildlife Insights, eMammal, Snapshot USA), iNaturalist, GBIF, Movebank and other GPS or biologging data, occurrence and museum records, trait databases, and IUCN range maps. Use before joining, merging, filtering, counting, or mapping species across datasets; when species columns don't line up; when a name may be an old synonym, a misspelling, a subspecies trinomial, or affected by a split or lump (for example Pecari tajacu vs Dicotyles tajacu); or when auditing a name-matching step. Core rule: resolve every name to its stable MDD species ID and compare IDs, never strings; the MDD synonym table maps the name, and an accepted name is never invented or one child of a split silently picked. Pin a specific MDD version."
---

# Reconciling mammal names against the MDD

## What this skill is for

You have mammal species names from two or more sources (two databases, an old
dataset and a new one, a field sheet and GBIF) and they don't line up: different
genus, an old synonym, a subspecies trinomial, a typo, a name that has since been
split or lumped. The job is to decide, for each name, *which currently recognized
species it refers to*, using the Mammal Diversity Database as the authority, and
then to tell whether two names from different sources are the same species or not.

Two modes, often together:

1. **Resolve** a list of names to current MDD-accepted species (with an explicit
   flag when a name can't be resolved to exactly one species).
2. **Reconcile** two or more lists against each other: run resolution on each,
   then join on the resolved MDD ID and report matches, mismatches, and
   unresolved names on either side.

Default to writing code the user runs. Match their stack (most reconciliation is
a pandas or dplyr join). Keep the original verbatim name in every output row.

## The one rule that matters most

**Resolve each name to the stable MDD species ID and compare IDs, not name
strings.** The MDD gives every accepted species a permanent integer ID (e.g.
`1006380` for *Dicotyles tajacu*). A name string is only a key into the MDD
tables; the ID is the identity. Two names refer to the same species iff they
resolve to the same ID. `Pecari tajacu`, `Dicotyles tajacu`, and `Tayassu tajacu`
are three strings and one ID.

Corollary, equally important: **the synonym table maps a name to an ID; the model
never invents the accepted name and never silently resolves a split.** If a name
maps to more than one current species (because it was split), the correct output
is *all candidates plus an ambiguous flag*, not a guess. "Unresolved" and
"ambiguous" are valid, correct answers. A pipeline that always emits one clean
accepted name is hiding its failures.

## What MDD gives you (and why not the taxon pages)

The per-species web pages at mammaldiversity.org are a rendering of underlying
CSVs. Don't scrape them. The download (one ZIP) contains three things this skill
uses:

- **Species list** — one row per currently accepted species, keyed by `id`, with
  `sciName`, `genus`, `specificEpithet`, authority, higher taxonomy,
  `countryDistribution`, `taxonomyNotes`, `flagged`, and cross-walk columns to
  MSW3 and CMW. This is the set of valid targets.
- **Synonym list** — 50,000+ historical / alternative species-rank names, each
  linked to the accepted species it belongs to, with its nomenclatural status
  (available, name_combination, incorrect_subsequent_spelling, unjustified
  emendation, ...). This is what turns an old or variant name into an ID.
- **Diff files** — tracked changes between adjacent versions, each classified
  (new / split / lump / genus change / common-name change). Use these when the
  question is "what happened to this name between version X and Y", not for
  routine resolution.

Field names and the exact synonym-file columns are documented in the metadata
file inside the ZIP. **Verify column names against that metadata on first use**;
`references/columns.md` lists the expected fields, and the resolver script prints
which columns it matched so you can catch a schema change.

Always **pin the version**. MDD releases roughly monthly and single releases can
carry 100+ changes. Record the version string (e.g. `MDD v2.4`) in every output.
Getting the latest release and version string: see `references/fetching_latest.md`.

## The procedure

Full detail in `references/resolution.md`; `references/change_types.md` explains
why each change type resolves the way it does. In brief, for each input name:

1. **Normalize** the string without discarding it. Trim and collapse whitespace;
   strip author and year; strip qualifiers (`cf.`, `aff.`, `sp.`, `?`); reduce a
   trinomial to its binomial *but keep the trinomial recorded*, since subspecies
   are below MDD's rank and the epithet may matter for a later split. Keep the
   verbatim original in its own column always.
2. **Exact match** the normalized binomial against accepted `sciName`. Hit →
   resolved, `match_type = accepted_exact`, done.
3. **Synonym match** against the synonym list. A synonym row links to an accepted
   species ID. One linked species → resolved, `match_type = synonym`, and record
   the synonym's nomenclatural status. This is where genus changes and lumps
   resolve automatically.
4. **Split check.** If the name links to **more than one** accepted species,
   return every candidate ID with `match_type = ambiguous_split`. Do not choose.
   Resolution now needs geography (`countryDistribution`) or the original
   subspecies epithet, applied by a human or an explicit rule, not the matcher.
5. **Fuzzy / structural fallback**, only if 2–4 miss: a unique epithet under a
   different genus, or a small edit distance, yields a *candidate* with
   `match_type = fuzzy` and low confidence, flagged for review. Never auto-accept
   a fuzzy hit.

   **Trap: never fall back to a bare-epithet match across genera.** A genus-change
   synonym (step 4) must be verified against the FULL historical binomial/trinomial
   — the synonym table's `MDD_original_combination` (or
   `MDD_normalized_original_combination`) column — never against the epithet alone
   (`MDD_root_name`) with the genus filter dropped. Epithets are reused across
   unrelated genera constantly (they're independent Latin/Greek adjectives), so a
   bare-epithet-only fallback WILL produce confident, wrong cross-family matches.
   Concrete case that surfaced this: resolving `Mazama nemorivaga` (a Neotropical
   brocket deer) against MDD v2.5 by matching the bare epithet "nemorivaga" in the
   synonym table returned `Bandicota indica` ("Greater Bandicoot Rat", an Old World
   murid rodent) — wrong family, wrong continent, wrong everything — because
   "nemorivaga" also happens to be a recorded historical epithet under `Bandicota`.
   The correct resolution (`Passalites nemorivagus`, following MDD's genus split of
   several former `Mazama` species into `Passalites`) only came from matching the
   verbatim two-word combination `"Mazama nemorivaga"` against
   `MDD_original_combination`, which is genus-specific by construction. Rule of
   thumb: any synonym lookup that drops the genus from the match key needs the
   full original combination string as its match key instead — spelling changes
   within a genus can safely match on epithet alone (step 3), but any lookup that
   is allowed to cross genus boundaries must require the full name to line up.
6. **Unresolved.** No defensible match → `match_type = unresolved` with a reason.
   Never fabricate an ID.

Then to **reconcile two lists**: resolve each side, join on resolved `id`, and
label each pair `same_species` (equal IDs), `different_species` (both resolved,
unequal), or `needs_review` (either side unresolved or ambiguous). Report the
three buckets separately.

`scripts/resolve_names.py` is a runnable reference implementation: it loads the
species and synonym CSVs, resolves a column of names, and can join two lists. It
is deliberately schema-defensive (fails loudly on a missing expected column
rather than guessing) and version-stamps its output.

## Non-negotiables (audit checklist)

- [ ] Every match is decided by an MDD table lookup, never by the model asserting
      an accepted name from memory. No ID originates from model weights.
- [ ] Output carries the **MDD version string**. An unversioned reconciliation is
      not reproducible.
- [ ] The **verbatim** input name and the **resolved** name+ID are both retained
      in every row.
- [ ] A name that maps to multiple current species is returned as
      `ambiguous_split` with all candidates, never collapsed to one.
- [ ] Comparison between sources is on **ID**, not on string equality of names.
- [ ] Fuzzy matches are labelled and never silently promoted to accepted.
- [ ] Any genus-change synonym match is verified against the full original
      combination string, never a bare epithet with the genus dropped (see the
      `Mazama nemorivaga` / `Bandicota indica` trap above).
- [ ] Failures return an explicit `unresolved` row with a reason, never a dropped
      row or a fabricated ID.
- [ ] Nomenclatural status of a synonym match is recorded (so a match via an
      incorrect subsequent spelling is distinguishable from a clean combination).

## Scope and honesty

MDD is species-level; subspecies are not accepted taxa, so a trinomial resolves
to its species and the subspecies information is preserved but not "recognized".
Splits are the genuine limit: when an old name now spans several species, the
name alone cannot say which, and geography only narrows it when ranges don't
overlap. Correct-but-coarse (or an honest "ambiguous") beats a confident wrong
assignment. MDD also makes documented subjective calls on contested groups (e.g.
its treatment of Groves & Grubb 2011 ungulates); when a downstream source follows
a different authority, the mismatch is real and should be reported, not smoothed
over.

Method reference for MDD itself: Burgin et al. (2025), "How many mammal species
are there now?"; the database DOI resolves to the current version.

## Existing tooling worth reusing

Don't rebuild what exists when the user prefers it:
- **`mdd_api`** (official Rust CLI) parses a release ZIP into typed records.
- **`rmdd`** (R, Santos) does MDD name lookup and synonym resolution directly.
- The website's search **exports CSV/JSON** with all fields for quick checks.

The bundled Python resolver exists so reconciliation can run as a self-contained
pandas job with the exact flagging logic above; point users to the R/Rust tools
when that fits their workflow better.

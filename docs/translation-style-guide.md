# Simplified Chinese Translation Style Guide

This guide defines shared language conventions for SCSP localization. It intentionally focuses on reusable translation quality rather than any particular translator or model.

## Priorities

When priorities conflict, use this order:

1. Preserve runtime structure and control syntax.
2. Preserve meaning and gameplay information.
3. Preserve established names and terminology.
4. Preserve character voice and scene context.
5. Produce natural, concise Simplified Chinese.
6. Preserve Japanese wording only when it is intentionally a name, brand, lyric source line, symbol, or other approved same-form content.

## Names and branding

Use `qa/names.json` and existing maintained translations as the canonical baseline for person names.

Unit names, song titles, product branding, abbreviations, and Latin-script proper names may intentionally remain unchanged. Do not translate a brand merely because the surrounding sentence is translated.

When a source name has multiple orthographic forms, such as normal spaces versus NBSP, keep the display translation consistent while preserving any layout-significant source structure required by the data surface.

## UI text

UI text should be brief and action-oriented.

Prefer established project terms. Avoid translating the same button or mechanic differently in neighboring screens without a contextual reason.

Do not add explanatory wording that is absent from the source if it makes the UI label materially longer.

## Gameplay terminology

Consult `qa/glossary.json`. For recurring systems, mechanics, currencies, and menu concepts, consistency is normally more valuable than a locally elegant synonym.

A glossary match is context guidance, not automatic global search-and-replace.

## Drama and scenario dialogue

Translate the speaker's intent and tone rather than mirroring Japanese word order.

Before translating a line, inspect nearby dialogue when possible. Pay attention to:

- who is speaking and to whom;
- honorific distance and politeness;
- repeated catchphrases;
- sentence continuation across multiple records;
- deliberate pauses, dashes, ellipses, and reaction sounds;
- line-break layout.

A source trailing newline can be serialization noise on some older scenario data. Do not add awkward visible whitespace only to satisfy a mechanical check; the public QA tool treats scenario layout differences as review signals rather than universal hard failures.

For current SCSP 2.17 Drama, use `scsp_localify/drama.json` together with the current source/context snapshot under `qa/current-source/`. The runtime identity is exact `uniqueId + source`; do not change either field. Bare `uniqueId` is not a sufficient global identity because current data contains duplicate unique IDs in several scenarios.

Use `python tools/prepare_drama_review.py` when an Agent or reviewer needs a flat record with scenario/order, speaker, source, maintained translation, and previous/next source context.

## Lyrics

The maintained `lyrics.json` convention often uses:

```text
Japanese source lyric
Simplified Chinese translation
```

The Japanese source prefix is intentional and must not be classified as untranslated residue. Review the appended translated portion independently.

Preserve lyric timing/segmentation semantics. Do not merge several source lyric keys into one target entry.

## Punctuation and typography

Use natural Simplified Chinese punctuation where it does not affect control syntax or a deliberate stylistic effect.

Do not normalize:

- placeholders;
- rich-text tags;
- sprite tags;
- format strings;
- resource identifiers;
- Unicode symbols with known UI meaning.

Full-width/half-width numeral or punctuation changes can affect exact display conventions. Treat them deliberately, especially in compact UI labels.

## Source-equal text

`source == translation` is not automatically wrong. Valid cases include:

- Latin branding;
- identifiers or labels intentionally displayed unchanged;
- proper names approved as same-form;
- motion/control strings;
- lyric entries not yet translated, which are review items rather than format errors.

Japanese prose left equal to source should normally be reviewed.

## Agent-assisted translation

Agents should receive:

- source text;
- stable identity (surface/table/key, Drama collision-safe/runtime-key identity, or legacy scenario path/key);
- nearby context when available;
- relevant glossary/name entries;
- existing exact-source translations and conflicts;
- explicit format-preservation constraints.

A model should never be asked to rewrite raw repository JSON without a validator between generation and merge.

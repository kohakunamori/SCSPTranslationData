# AGENTS.md

This repository contains the public Simplified Chinese localization data for SCSP. This file is the primary operating guide for coding and translation agents working in the repository.

## Scope and repository boundary

- Work on the maintained `TransData` branch unless the task explicitly targets another branch.
- `DumpData` is a source-text reference branch. It can lag the current client and must not be treated as authoritative for newly added text without verification.
- Keep this repository self-contained and public. Do not add private project details, local machine paths, account data, tokens, cookies, captures, logs, game binaries, or unpublished runtime infrastructure.
- Do not add official game assets unless they are already part of the repository and allowed by the repository license and project policy.

## Data surfaces

| Path | Meaning | Editing rule |
| --- | --- | --- |
| `scsp_localify/localify.json` | Main localization tables | Preserve table names and keys; edit user-visible values only |
| `scsp_localify/local2.json` | Exact-source string map | Keys are source text; normally edit values only |
| `scsp_localify/lyrics.json` | Lyric source-to-display map | Keys are source lyrics; preserve the established bilingual format |
| `scsp_localify/drama.json` | Current SCSP 2.17 Drama consumer translation | Runtime identity is exact `uniqueId + source`; preserve identity/source metadata and edit `text` only |
| `scsp_localify/scenario/**/*.json` | Scenario dialogue | Preserve file path, record order, `key`, and JSON shape; edit `text` only |
| `qa/` | Public translation policy and QA knowledge | Keep rules generic, reviewable, and documented |
| `tools/` | Public QA and maintenance tools | Must use only public repository inputs |

## Before editing

1. Run `git status --short --branch`. Do not overwrite unrelated local changes.
2. Identify the data surface and obtain the best available Japanese source/context.
3. Check `qa/glossary.json`, `qa/names.json`, existing translations, and translation-memory output before inventing a new term.
4. Make the smallest coherent change. Never reformat large JSON files just to change a few values.
5. Do not change keys to "fix" source text. A key may be an identifier or an exact-source lookup key.
6. For Drama/scenario dialogue, inspect nearby lines so pronouns, speaker tone, terminology, and line breaks remain coherent. For current Drama, prefer the adjacent context already published in `qa/current-source/drama-2.17-source.json.gz`.

## Required quality rules

Read `docs/qa-policy.md` and `docs/community-quality-backlog.md` when changing validators, exceptions, backlog classification, or QA policy.

Hard failures are structural or runtime-safety problems and must be fixed before submission:

- invalid JSON;
- missing or duplicated scenario keys introduced by an edit;
- changed table/key identity where the format requires stable keys;
- lost or altered format placeholders such as `{0}`, printf-style placeholders, or rich-text tags;
- accidental secret/local-path leakage detected by the public QA tool.

Review warnings are semantic signals and require judgement rather than blind replacement:

- remaining Japanese kana;
- source text left unchanged;
- inconsistent translations for an identical source;
- glossary disagreement;
- numeric, percentage, NBSP, or newline-shape differences on surfaces where those differences can be legitimate.

Do not silence a warning by making a worse translation. If the existing form is intentional, document or whitelist it through the public QA policy.

Exact-source translations that differ only by ordinary/NBSP/full-width display spacing are layout variants, not automatic terminology conflicts. Canonical same-form names in `qa/names.json` do not need duplicate entries in `qa/allowed-source-equal.json`.

`qa/baseline-exceptions.json` is only for anomalies that predate the public QA gate. Do not add new entries merely to make CI pass; fix new defects instead.

For repository-wide cleanup, generate the structured backlog:

```bash
python tools/build_quality_backlog.py
```

Prefer bounded P1/P2/category batches. Never treat `agent_ready=true` as permission to auto-apply; every generated item has `auto_apply_allowed=false`.

## Lyrics policy

`lyrics.json` commonly keeps the Japanese source line and appends the Simplified Chinese translation on a following line. Therefore Japanese text in the preserved source prefix is not itself a defect. Review the translated portion separately.

Do not remove source lyric text merely to satisfy a kana-residue checker.

## Agent-assisted translation workflow

Recommended flow:

1. For `localify` and current Drama, use the bundled 2.17 source snapshots under `qa/current-source/` before consulting historical `DumpData`. For legacy scenario or other surfaces, establish current source provenance before source-sensitive edits.
2. Reuse exact, unambiguous existing translations where context is compatible.
3. Apply the reviewed glossary and canonical names.
4. Translate only unresolved source text.
5. Run:
   ```bash
   python tools/qa.py
   python tools/audit_current_localizetext.py
   python tools/audit_current_drama.py
   ```
6. When a `DumpData` ref is available, build a public translation-memory view:
   ```bash
   python tools/build_translation_memory.py
   ```
7. For bulk unresolved work, generate a deterministic source-deduplicated batch:
   ```bash
   python tools/prepare_agent_batch.py
   ```
   By default, this only emits unresolved records whose source identity is available from a maintained source-key surface. If a dump has been independently verified as current, opt in explicitly:
   ```bash
   python tools/prepare_agent_batch.py --dump-ref <current-source-ref> --authoritative-dump
   ```
   For current Drama review, use the dedicated context-rich view:
   ```bash
   python tools/prepare_drama_review.py
   ```
8. Validate structured Agent output before applying it:
   ```bash
   python tools/validate_agent_result.py qa/generated/agent-batch.jsonl path/to/result.jsonl
   ```
9. Review every hard failure and relevant warning.
10. Check strict exact-source consistency:
    ```bash
    python tools/canonicalize_exact_source_conflicts.py --check
    ```
11. For quality-debt work, regenerate the backlog and enforce the current-source gate:
    ```bash
    python tools/build_quality_backlog.py --check-current-key
    ```
    Confirm the intended backlog ID disappears or is narrowly reclassified.
12. Inspect `git diff --check` and the semantic diff before committing.

Agent output is judged by the same QA gates as human output. Do not merge raw model output without validation.

The public interchange schemas live under `qa/schemas/`. Do not invent a private-only result format when the public schema is sufficient.

Do not use `--authoritative-dump` for the historical `DumpData` branch merely to increase batch size.

The current localizetext snapshot is a source-coverage anchor, not a request to force source/target runtime templates into textual identity. A Japanese source can contain a concrete number or layout token while the maintained localized value intentionally uses a runtime placeholder or different wrapping. Use `audit_current_localizetext.py` for full current-version coverage/kana closure and keep `qa.py` for its documented review semantics.

For current Drama, the plugin lookup key is exact `uniqueId + source`. Do not rewrite `uniqueId` or source text to make a translation easier to match. Eight current scenarios contain duplicate bare unique IDs, so Agent tooling should use the published collision-safe identity and runtime-key identity rather than assuming `uniqueId` alone is globally unique.

The current Drama snapshot is not the same surface as legacy `scsp_localify/scenario/**/*.json`; do not transfer provenance assumptions between them.

Historical `prepare_agent_batch.py` skip counts are not current localify defect counts. Current localify completeness is defined by the current-source audit.

`canonicalize_exact_source_conflicts.py` is intentionally conservative. It only proposes a change when `local2` is the sole outlier in a two-way exact-source conflict, all maintained `localify` occurrences unanimously use the other target, the difference is not spacing-only, and protected/layout/numeric signatures are compatible. Review the proposal before using `--apply`.

Numeric QA recognizes a small set of target-side CJK-number equivalents only to satisfy explicit numeric tokens already present in the source. Never broaden this into arbitrary Chinese-number extraction: phrases such as `上一个` must not create a numeric warning.

## Translation style

Read `docs/translation-style-guide.md` before broad translation work. In particular:

- prefer established project terminology over literal one-off variants;
- preserve names and unit/song branding according to repository conventions;
- keep UI wording concise;
- translate meaning and character voice, not Japanese syntax;
- preserve deliberate punctuation, control tags, and layout constraints where they affect rendering.

## Version updates

Read `docs/version-update-workflow.md`. Existing `update_local_json.py` performs key-level carry-forward only; it does not prove that a source meaning is unchanged. New or changed source text still needs review.

## Pull requests and commits

- Keep translation PRs scoped by surface, story set, table, or version update when practical.
- Explain whether the change is human-authored, agent-assisted, or mechanically migrated when that matters to review.
- Include the QA result and before/after backlog counts in the PR description for bulk quality-cleanup changes.
- Generated local QA reports and translation-memory output are working artifacts unless a maintainer explicitly chooses to version them.

## Privacy check

Before committing, confirm the diff does not contain:

- absolute personal filesystem paths;
- usernames, account IDs, cookies, tokens, authorization headers, or startup secrets;
- private service endpoints or private infrastructure;
- debugging captures/logs unrelated to public translation review;
- references to non-public repositories or internal-only workflows.

When uncertain, keep the public contribution limited to translation data, reproducible public-source metadata, and generic QA logic.

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
| `scsp_localify/scenario/**/*.json` | Scenario dialogue | Preserve file path, record order, `key`, and JSON shape; edit `text` only |
| `qa/` | Public translation policy and QA knowledge | Keep rules generic, reviewable, and documented |
| `tools/` | Public QA and maintenance tools | Must use only public repository inputs |

## Before editing

1. Run `git status --short --branch`. Do not overwrite unrelated local changes.
2. Identify the data surface and obtain the best available Japanese source/context.
3. Check `qa/glossary.json`, `qa/names.json`, existing translations, and translation-memory output before inventing a new term.
4. Make the smallest coherent change. Never reformat large JSON files just to change a few values.
5. Do not change keys to "fix" source text. A key may be an identifier or an exact-source lookup key.
6. For scenario dialogue, inspect nearby lines so pronouns, speaker tone, terminology, and line breaks remain coherent.

## Required quality rules

Read `docs/qa-policy.md` when changing validators, exceptions, or QA policy.

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

`qa/baseline-exceptions.json` is only for anomalies that predate the public QA gate. Do not add new entries merely to make CI pass; fix new defects instead.

## Lyrics policy

`lyrics.json` commonly keeps the Japanese source line and appends the Simplified Chinese translation on a following line. Therefore Japanese text in the preserved source prefix is not itself a defect. Review the translated portion separately.

Do not remove source lyric text merely to satisfy a kana-residue checker.

## Agent-assisted translation workflow

Recommended flow:

1. Compare the current source dump with existing `TransData`.
2. Reuse exact, unambiguous existing translations where context is compatible.
3. Apply the reviewed glossary and canonical names.
4. Translate only unresolved source text.
5. Run:
   ```bash
   python tools/qa.py
   ```
6. When a `DumpData` ref is available, build a public translation-memory view:
   ```bash
   python tools/build_translation_memory.py
   ```
7. For bulk unresolved work, generate a deterministic source-deduplicated batch:
   ```bash
   python tools/prepare_agent_batch.py
   ```
8. Validate structured Agent output before applying it:
   ```bash
   python tools/validate_agent_result.py qa/generated/agent-batch.jsonl path/to/result.jsonl
   ```
9. Review every hard failure and relevant warning.
10. Inspect `git diff --check` and the semantic diff before committing.

Agent output is judged by the same QA gates as human output. Do not merge raw model output without validation.

The public interchange schemas live under `qa/schemas/`. Do not invent a private-only result format when the public schema is sufficient.

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
- Include the QA result in the PR description for bulk changes.
- Generated local QA reports and translation-memory output are working artifacts unless a maintainer explicitly chooses to version them.

## Privacy check

Before committing, confirm the diff does not contain:

- absolute personal filesystem paths;
- usernames, account IDs, cookies, tokens, authorization headers, or startup secrets;
- private service endpoints or private infrastructure;
- debugging captures/logs unrelated to public translation review;
- references to non-public repositories or internal-only workflows.

When uncertain, keep the public contribution limited to translation data, reproducible public-source metadata, and generic QA logic.

# Contributing to SCSPTranslationData

Thank you for improving the Simplified Chinese localization.

The project accepts both human and agent-assisted contributions. The acceptance criterion is translation quality and reproducibility, not which tool produced the first draft.

## Choose a contribution path

### Small manual correction

Use this path for typos, terminology fixes, individual UI strings, lyrics corrections, or a bounded scenario edit.

1. Branch from `TransData`.
2. Modify only the necessary values.
3. Preserve keys, paths, tags, placeholders, and JSON structure.
4. Run `python tools/qa.py`.
5. Open a PR explaining the affected surface and reason for the change.

### Agent-assisted or bulk translation

Read `AGENTS.md` and `docs/agent-translation-guide.md` first.

For validator behavior, warning policy, historical baseline exceptions, and repository-wide cleanup, also read `docs/qa-policy.md` and `docs/community-quality-backlog.md`.

Bulk work should:

- use the current Japanese source when available;
- consult the public glossary and existing translation memory;
- deduplicate identical source strings before model dispatch where context permits;
- preserve source identity in the work manifest;
- pass structural/format QA;
- review semantic warnings rather than suppressing them mechanically.

Raw, unreviewed machine translation should not be submitted as the final dataset.

### Client-version update

Follow `docs/version-update-workflow.md`.

The `DumpData` branch is useful historical source material but can lag the current client. For `localify` and current Drama, prefer the bundled current-version snapshots under `qa/current-source/`; for legacy scenario and other surfaces, prefer independently verified current-client source data.

## Repository invariants

Do not change:

- `localify.json` table/key identity merely to alter displayed text;
- `local2.json` source keys;
- `lyrics.json` source keys;
- scenario file paths or scenario `key` values without a format/source migration reason.

Do not mass-reformat JSON files in a translation-only PR.

## Quality gates

Run:

```bash
python -m unittest discover -s tools -p "test_*.py"
python tools/qa.py
python tools/audit_current_localizetext.py
python tools/audit_current_drama.py
python tools/canonicalize_exact_source_conflicts.py --check
python tools/build_quality_backlog.py --check-current-key
git diff --check
```

The QA tool separates hard errors from review warnings.

Hard errors are expected to block a PR. Warnings may be acceptable, but bulk changes should explain intentional exceptions when they are material.

For translation-memory inspection:

```bash
python tools/build_translation_memory.py
```

Generated output goes under `qa/generated/` and is not committed by default.

The current SCSP 2.17 `localizetext` and Drama source anchors are committed under `qa/current-source/`. Do not replace them with a local dump or regenerate their manifests without documenting the client version, deterministic hashes, and source-universe counts. See [docs/current-source-snapshot.md](docs/current-source-snapshot.md).

For current Drama edits, preserve `scenarioId`, `sourceSchema`, `uniqueId`, `source`, and `talkerName`; edit only `text`. The runtime key is exact `uniqueId + source`, and `uniqueId` alone is not a safe identity.

For an actionable, deduplicated quality-debt view:

```bash
python tools/build_quality_backlog.py
```

For exact-source conflicts, preview the repository's conservative canonicalization proposal with:

```bash
python tools/canonicalize_exact_source_conflicts.py
```

Do not use `--apply` as a general translation command. The tool only handles the narrow two-way/local2-outlier case documented in `AGENTS.md`.

When a PR is specifically fixing quality debt, include the affected backlog IDs or category/priority slice and the before/after backlog counts.

## Terminology

Reviewed shared terminology lives in `qa/glossary.json`; canonical person-name mappings live in `qa/names.json`.

A glossary entry is a project convention, not a license to replace substrings blindly. Context-sensitive Japanese can require different Chinese wording. If an established term is wrong, update the glossary and affected translations together with a rationale.

## Pull request description

For non-trivial changes, include:

- surface or story/table scope;
- source provenance, when relevant;
- whether translation was manual, agent-assisted, or mechanically migrated;
- QA summary;
- known warnings or intentional exceptions;
- screenshots only when they are useful and contain no private/account information.

The repository's GitHub Pull Request template asks for the same information, including source provenance and before/after QA/backlog counts. Translation-quality and source/version-update Issue forms are also available under `.github/ISSUE_TEMPLATE/`.

## Public-repository privacy

Never commit personal paths, account information, cookies, tokens, private endpoints, unpublished infrastructure, unrelated logs/captures, or private project details.

Public QA tools must be runnable from this repository using public repository inputs.

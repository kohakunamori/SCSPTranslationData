# Translation QA Policy

This document explains how the public QA layer distinguishes blockers, review backlog, and known historical exceptions.

## Goals

The QA system should do two things at the same time:

1. prevent new structural/runtime-breaking translation defects;
2. expose existing semantic quality debt so the community can improve it incrementally.

It must not make every future PR fail merely because the repository already contains older anomalies.

## Hard errors

A hard error means the current contribution is unsafe to merge without an explicit policy change.

Examples include:

- invalid JSON or wrong top-level data shape;
- newly introduced duplicate scenario keys not present in the reviewed baseline exception set;
- lost brace/printf/rich-text tokens when the source identity is authoritative;
- public-repository privacy leakage such as personal absolute paths or bearer credentials.

When source text comes only from the historical `DumpData` branch, source-derived differences are warnings by default because that branch can lag the current client.

For the main `localify` surface, the repository now carries a separate current SCSP 2.17.0 source snapshot under `qa/current-source/`. Its authoritative coverage gate is:

```bash
python tools/audit_current_localizetext.py
```

This gate requires every current source table/key to map to a maintained translation and rejects current same-kana or translated-kana-residual rows. The accepted checkpoint is **138,036 / 138,036 mapped / 0 missing / 0 actionable**.

It intentionally does **not** require source and target placeholder, rich-text, numeric, newline, or NBSP signatures to be identical. Current Japanese `localizetext` may contain concrete/static values while the maintained localization uses runtime templates or different display wrapping. Applying the generic signature rules to the entire current source universe would create false blockers.

If a contributor has verified that a dump/ref is current and authoritative, run:

```bash
python tools/qa.py --dump-ref <ref> --authoritative-dump
```

That promotes configured source-format checks for dump-backed surfaces to hard gates.

## Review warnings

Warnings are a public quality backlog. They are deliberately not auto-fixed.

Current categories include:

- source-equal Japanese text;
- remaining kana in translated portions;
- exact source strings with multiple maintained translations;
- glossary disagreement;
- numeric/percentage differences;
- newline, CR, or NBSP differences;
- source-format differences observed only against a non-authoritative historical dump;
- known historical duplicate scenario keys.

A warning can indicate a real translation problem, a context-sensitive translation, a name/brand, a lyric convention, or harmless serialization/layout drift.

Exact-source conflicts are split by semantics: if maintained outputs differ only by ordinary spaces, NBSP, or full-width spaces, QA reports `duplicate-source-layout-variant` and the backlog treats it as P3 layout debt instead of a P2 semantic conflict. Canonical names whose reviewed source and translation are the same are also accepted as same-form automatically.

Backlog entries with historical `DumpData` provenance carry `requires_source_verification=true`. This is especially important for protected-format and numeric findings: a P1/P2 priority indicates review value, not permission to repair against a stale source snapshot.

Numeric comparison is intentionally asymmetric. Explicit Arabic/full-width numeric tokens in the source remain the anchor; target-side Chinese forms are used only to fill those source-token deficits for reviewed patterns such as `4 → 四名`, `2 → 两行`, `1 → 第一季`, `10 → 十次`, and `2倍 → 翻倍`. Chinese numerals are not independently harvested from arbitrary target prose, avoiding false positives such as `上一个`.

When a semantic equivalence is real but too context-specific to generalize, `qa/rules.json` may contain an exact `reviewed_semantic_exceptions` row keyed by QA code, surface, exact source, and exact translation. Broad ignore patterns are not acceptable.

Warnings are converted into stable, deduplicated community review tasks with:

```bash
python tools/build_quality_backlog.py
```

See [community-quality-backlog.md](community-quality-backlog.md). The backlog distinguishes P1/P2/P3 and intentionally collapses repeated manifestations of the same structural debt where appropriate.

False positives should be reduced through the narrowest reviewed policy. For example, kana-bearing song titles that intentionally remain Japanese belong in `kana_preserve_terms`; broad kana ignores are not acceptable.

## Baseline exceptions

`qa/baseline-exceptions.json` records anomalies that existed before the public QA gate was introduced.

These entries are **not** general permission to ignore the rule. They serve as a narrow grandfathered baseline so that:

- existing data remains buildable/reviewable;
- newly introduced instances still fail;
- the community can remove exceptions over time by fixing the underlying data.

When an exception is fixed, delete the corresponding baseline entry in the same PR.

Adding a new baseline exception should be rare and requires a clear public reason. Prefer fixing the data.

## Glossary and names

`qa/glossary.json` and `qa/names.json` are reviewable public knowledge.

Glossary mismatches are warnings because identical Japanese terms can be context-sensitive. Do not perform blind global replacement just to make the warning count smaller.

When community consensus changes a canonical term:

1. update the glossary/name policy;
2. update affected maintained translations where appropriate;
3. run QA;
4. explain the migration in the PR.

## Translation memory

Generate the current public translation-memory view with:

```bash
python tools/build_translation_memory.py
```

The generated files are intentionally ignored by Git:

- `qa/generated/translation-memory.jsonl`;
- `qa/generated/translation-memory-conflicts.json`;
- `qa/generated/translation-memory-summary.json`.

The memory includes stable public identity and provenance. Conflict entries must be reviewed before automatic reuse.

Generated summaries use repository-relative paths so they do not leak a contributor's local filesystem layout.

## Exact-source canonicalization

`tools/canonicalize_exact_source_conflicts.py` handles one conservative consistency case: `local2` is the sole outlier in a two-target exact-source conflict while every `localify` occurrence unanimously uses the other target. Spacing-only variants and any protected/layout/numeric incompatibility are excluded.

The default command writes a proposal only. `--apply` is an explicit mutation, and CI uses `--check` to require the strict candidate set to stay empty.

## Current-key gate

`tools/build_quality_backlog.py --check-current-key` fails when a non-exempt backlog item is sourced from a maintained current source-key surface. The exemption list lives in `qa/backlog-policy.json` and is intentionally narrow. Historical `DumpData` tasks never pass this gate merely because they have a high P1/P2 priority.

## CI

`.github/workflows/translation-qa.yml` runs the same public `tools/qa.py` entry point used locally.

CI publishes:

- a JSON QA report artifact;
- a Markdown job summary.
- a current-localizetext coverage audit JSON/Markdown artifact;
- a generated quality-backlog JSONL and JSON/Markdown summary artifact.
- an exact-source canonicalization proposal artifact.

Warnings remain visible for community cleanup without globally blocking historical debt. Hard errors, current-localizetext missing/actionable rows, strict canonicalization candidates, and non-exempt current-key backlog items fail the job.

## Improving the QA system

Good QA changes should be:

- deterministic;
- standard-library-only where practical;
- runnable from a fresh public clone;
- independent of private services or devices;
- explicit about false-positive tradeoffs;
- documented in this file and `AGENTS.md`.

If a new check needs data that cannot be published, it does not belong in this public QA gate.

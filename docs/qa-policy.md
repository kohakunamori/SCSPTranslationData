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

## CI

`.github/workflows/translation-qa.yml` runs the same public `tools/qa.py` entry point used locally.

CI publishes:

- a JSON QA report artifact;
- a Markdown job summary.

Warnings remain visible for community cleanup without blocking unrelated contributions; hard errors fail the job.

## Improving the QA system

Good QA changes should be:

- deterministic;
- standard-library-only where practical;
- runnable from a fresh public clone;
- independent of private services or devices;
- explicit about false-positive tradeoffs;
- documented in this file and `AGENTS.md`.

If a new check needs data that cannot be published, it does not belong in this public QA gate.

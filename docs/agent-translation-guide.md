# Agent Translation Guide

This document describes a model-agnostic workflow for using translation agents safely in SCSPTranslationData.

## Principle

Treat an agent as a translation worker, not as the source of truth. Stable source identity, deterministic preprocessing, automated validation, and human/community review remain authoritative.

## Recommended pipeline

```text
current source dump
        |
        v
stable key/path alignment
        |
        v
exact-source translation memory
        |
        v
glossary + canonical names
        |
        v
deduplicated unresolved sources
        |
        v
translation agent
        |
        v
hard structural validation
        |
        v
semantic warning review
        |
        v
repository diff + CI
```

## Input records

For bulk work, give each source a stable record rather than asking a model to edit repository files directly. A useful record contains:

```json
{
  "source_id": "stable-public-id",
  "surface": "localify",
  "table": "example_table",
  "key": "123",
  "source": "Japanese source text",
  "context_before": null,
  "context_after": null
}
```

For scenario work, use scenario path/key and nearby dialogue as context.

The repository can generate these records directly:

```bash
python tools/prepare_agent_batch.py
```

The default batch intentionally excludes unresolved `localify`/scenario records whose Japanese source is known only through the historical `DumpData` reference. If a dump/ref has been independently verified against the current client, it may be enabled explicitly:

```bash
python tools/prepare_agent_batch.py \
  --dump-ref <current-source-ref> \
  --authoritative-dump
```

Never mark historical `DumpData` authoritative simply to make more rows available to an Agent.

If all maintained source-key text is already resolved, the default Agent batch can legitimately be empty. This does not mean historical `localify`/scenario backlog is solved; it means that work is intentionally blocked on current-source verification.

The canonical public record schema is `qa/schemas/agent-batch-record.schema.json`.

## Translation memory

Run:

```bash
python tools/build_translation_memory.py
```

The generated memory aligns the public `DumpData` reference with maintained `TransData` wherever stable identity is available.

Rules for automatic reuse:

- reuse only exact, unambiguous source mappings by default;
- send conflicting mappings to review;
- do not assume two identical short labels have identical meaning across unrelated UI contexts;
- prefer current context over historical memory when they conflict.

## Glossary injection

Pass only relevant glossary terms to each worker. A smaller contextual glossary is easier for a model to obey than a large unrelated dictionary.

Do not force a preferred term when the current sentence uses the same Japanese string in a materially different sense.

## Worker output

Prefer structured JSONL or another strict schema. At minimum preserve:

- stable source ID;
- exact source text;
- translated text;
- an explicit decision such as `translate` or `needs_review`;
- a short note for uncertain/context-sensitive cases.

Do not allow a worker to silently add/drop records.

The canonical public result schema is `qa/schemas/agent-result-record.schema.json`.

Before applying any worker output:

```bash
python tools/validate_agent_result.py \
  qa/generated/agent-batch.jsonl \
  path/to/agent-result.jsonl
```

This checks exact source identity and coverage plus protected format signatures. Numeric/percentage changes and residual kana are surfaced as review warnings.

After applying reviewed results, also run:

```bash
python tools/canonicalize_exact_source_conflicts.py --check
python tools/build_quality_backlog.py --check-current-key
```

The first prevents reintroducing mechanically closable exact-source divergence; the second prevents new quality debt on maintained source-key surfaces.

## Hard validation

Before applying model output, reject records that:

- have unknown or duplicate source IDs;
- changed the source identity;
- are missing required output;
- break placeholders or rich-text tags;
- break a required JSON/schema invariant.

The repository-wide `tools/qa.py` provides a second validation layer after data is applied.

## Semantic review warnings

Warnings should be reviewed, not blindly "fixed":

- remaining kana;
- unchanged Japanese;
- differing translations for identical source;
- glossary disagreement;
- unexpected numeric or layout changes.

Some warnings are legitimate due to names, lyrics, stylistic context, or serialization differences.

## Review strategy

For large batches, review risk rather than random rows only. Prioritize:

1. hard-validator rejects;
2. glossary conflicts;
3. format/layout warnings;
4. Japanese residue;
5. identical source with conflicting targets;
6. very short/context-sensitive labels;
7. long dialogue and gameplay-rule text.

A second agent can review the first agent's output, but it should receive the original Japanese and the same stable identity rather than only the proposed Chinese translation.

## Quality-backlog review

Translation generation and quality-debt review are separate workflows. For existing repository warnings, use:

```bash
python tools/build_quality_backlog.py --agent-ready-only
```

To focus on the highest-priority review slice:

```bash
python tools/build_quality_backlog.py --priority P1 --agent-ready-only
```

Each backlog record includes source identity/provenance, category, priority, and a recommended review action. `agent_ready` means an Agent can assist with review; it does **not** mean the proposed change may be applied automatically. `auto_apply_allowed` is always false.

## Reproducibility

Record enough public information to reproduce a batch:

- source ref/dump provenance;
- source IDs;
- glossary revision;
- tool revision;
- QA report;
- final PR/commit.

Do not record private machine paths, credentials, or internal infrastructure in public metadata.

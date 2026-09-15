# Community Translation Quality Backlog

The public QA system can turn repository-wide warnings into a deterministic, reviewable backlog instead of an unstructured warning count.

## Generate the backlog

Run:

```bash
python tools/build_quality_backlog.py
```

Generated files are written under `qa/generated/` and are ignored by Git:

- `quality-backlog.jsonl`: one stable review task per unique backlog item;
- `quality-backlog-summary.json`: machine-readable counts;
- `quality-backlog-summary.md`: human-readable summary.

The item format is documented by `qa/schemas/quality-backlog-item.schema.json`.

## Priorities

Priority is about review urgency, not permission to edit automatically.

| Priority | Meaning |
| --- | --- |
| P1 | High-value review: protected runtime syntax or likely untranslated/residual Japanese |
| P2 | Semantic consistency: terminology, same-source conflicts, numbers/percentages |
| P3 | Layout or grandfathered structural debt that needs cautious/manual review |

The detailed mapping lives in `qa/backlog-policy.json`.

Every generated item has:

```json
"auto_apply_allowed": false
```

An Agent may propose a fix, but must not automatically apply a backlog item merely because it is marked `agent_ready`.

## Useful filters

Only P1:

```bash
python tools/build_quality_backlog.py --priority P1
```

Only Agent-ready tasks:

```bash
python tools/build_quality_backlog.py --agent-ready-only
```

One category:

```bash
python tools/build_quality_backlog.py --category terminology
```

Small review batch:

```bash
python tools/build_quality_backlog.py \
  --priority P2 \
  --category terminology \
  --agent-ready-only \
  --max-items 50
```

Custom output paths can be supplied with `--output`, `--summary`, and `--markdown`.

## Categories

Current public categories include:

- `protected-format`: braces, printf tokens, and rich-text tags;
- `untranslated-or-intentional`: source-equal Japanese/Han text that needs classification;
- `terminology`: glossary disagreement;
- `source-consistency`: the same Japanese source has multiple maintained Chinese outputs;
- `display-spacing-variant`: the same source has translations that are textually identical after removing ordinary/NBSP/full-width display spacing;
- `numeric-semantics`: numeric or percentage signatures differ;
- `layout`: CR/LF/NBSP differences;
- `baseline-format`: known protected-format anomaly that predates the QA gate;
- `baseline-structure`: known duplicate scenario-key debt that predates the QA gate.

Categories can be refined as false positives are understood. A good QA change reduces noise without hiding genuine defects.

## Provenance matters

Many `localify.json` and scenario comparisons currently use the public historical `DumpData` branch.

A backlog item whose provenance points to `DumpData` is **not proof that the current client source is identical**. Before changing placeholders, numbers, percentages, or source-sensitive wording, verify the current authoritative source when possible.

By contrast, `local2.json` and `lyrics.json` use source strings as keys, so their source identity is directly available from the maintained data.

Generated items make this explicit when provenance is available:

- `source_authority=current-key` / `requires_source_verification=false`: source identity comes from a maintained source-key surface;
- `source_authority=historical-reference` / `requires_source_verification=true`: source came from historical `DumpData` and must be rechecked before source-sensitive repairs.

## Recommended community workflow

1. Generate the current backlog.
2. Pick a bounded priority/category batch.
3. Read `AGENTS.md`, the translation style guide, glossary/name policy, and relevant context.
4. Verify current source provenance where required.
5. Fix the underlying translation or policy—not the generated backlog file.
6. Run:
   ```bash
   python tools/qa.py
   python tools/canonicalize_exact_source_conflicts.py --check
   python tools/build_quality_backlog.py --check-current-key
   git diff --check
   ```
7. Confirm the target backlog item disappears or is intentionally reclassified.
8. Submit a scoped PR with the before/after QA/backlog counts.

Do not commit `qa/generated/` output unless maintainers explicitly decide to freeze a snapshot.

## Resolving false positives

If an item is intentional, prefer the narrowest public policy representation:

- reviewed same-form string -> `qa/allowed-source-equal.json`;
- canonical name -> `qa/names.json`; names whose canonical source/translation are the same are automatically treated as reviewed same-form, including ordinary/NBSP/full-width spacing variants;
- terminology -> `qa/glossary.json`;
- allowed kana-bearing title/brand -> `kana_preserve_terms` in `qa/glossary.json`;
- exact semantic numeric/layout equivalence that cannot be generalized safely -> an exact `reviewed_semantic_exceptions` entry in `qa/rules.json`;
- pre-existing structural/format anomaly -> `qa/baseline-exceptions.json` only when it genuinely predates the public QA gate.

Do not add broad ignore patterns simply to reduce counts.

## Current direction

The backlog should be driven toward zero by:

1. removing false positives through narrow reviewed policy;
2. fixing high-confidence P1 defects;
3. resolving genuine untranslated/source-equal content;
4. consolidating terminology and exact-source conflicts;
5. addressing layout and historical structure only with rendering/source evidence.

The generated summary, not a hard-coded number in documentation, is the authoritative current count.

## Verified checkpoint

At the September 15, 2026 current-source closure checkpoint, the full repository QA is **0 hard errors / 2,077 review warnings**. The deduplicated backlog is **2,030 tasks**: **35 P1 / 1,084 P2 / 911 P3**.

At this checkpoint:

- the strict exact-source canonicalizer reports **0 candidates**;
- the `current-key` backlog gate reports **0 blockers**; the only current-key item is the explicitly grandfathered legacy `baseline-format` fixture;
- the default Agent batch has **0 verified-current unresolved records**;
- **732 historical Dump-only sources / 2,020 occurrences** remain isolated until their source is verified against a current client dump;
- the remaining repository backlog is therefore historical-reference debt plus the one documented baseline fixture, not a claim that all 2,077 warnings are defects in the current client.

Regenerate locally for authoritative current counts.

## Exact-source canonicalization

The repository includes a deliberately narrow helper:

```bash
python tools/canonicalize_exact_source_conflicts.py
```

It emits a proposal only. A candidate must satisfy all of the following:

- exact Japanese source identity;
- exactly two maintained targets;
- `local2` is the sole divergent target;
- every other maintained occurrence is `localify` and unanimously uses one target;
- the difference is not only ordinary/NBSP/full-width spacing;
- protected tokens, tags, LF/CR/NBSP structure, numeric semantics, and percentages are compatible.

After review, maintainers may apply the deterministic proposal with `--apply`. CI runs `--check` and fails if such mechanically closable conflicts are reintroduced.

## Current-source gate

```bash
python tools/build_quality_backlog.py --check-current-key
```

This gate considers only backlog entries with `source_authority=current-key`. Categories listed in `current_key_gate_exempt_categories` are explicit reviewed baselines; all other current-key items fail the command. Historical `DumpData` warnings remain visible without being promoted to current-source blockers.

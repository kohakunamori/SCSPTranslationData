# Current SCSP 2.17 Source Snapshot

This repository publishes a self-contained current-source anchor for the main `localify.json` surface.

## Files

- `qa/current-source/localizetext-2.17-source.json.gz`
  - full current SCSP 2.17.0 `localizetext` source universe;
  - JSON shape after decompression: `table -> key -> Japanese source text`;
  - 5,631 tables;
  - 138,036 source rows.
- `qa/current-source/localizetext-2.17-qa-scope.json.gz`
  - migration/reference subset limited to table/key identities that existed in the historical public `DumpData` localify coverage;
  - source values still come from the current 2.17.0 snapshot;
  - 1,629 tables / 39,711 rows.
- `qa/current-source/manifest.json`
  - version, counts, deterministic hashes, and historical-comparison metadata.

The gzip files are deterministic (`mtime=0`). The manifest records both compressed and uncompressed SHA-256 values so contributors can verify the snapshot without any private environment.

## Why this exists

The historical public `DumpData` branch is useful for legacy alignment, but it is not a reliable current-source authority.

Stable table/key comparison against the current 2.17.0 snapshot shows:

| Metric | Count |
| --- | ---: |
| Historical localify rows | 44,860 |
| Historical rows still present in current 2.17 | 39,711 |
| Historical rows no longer present | 5,149 |
| Unchanged source values on the overlap | 36,115 |
| Changed source values on the overlap | 3,596 |
| Current rows absent from historical DumpData | 98,325 |

That means **9.06%** of the still-existing historical overlap changed source text, while most current 2.17 rows were never present in the old public dump at all.

Do not treat `DumpData` source text as current merely because table/key identity still exists.

## Current coverage gate

Run:

```bash
python tools/audit_current_localizetext.py
```

The audit joins every current snapshot table/key to maintained `scsp_localify/localify.json`.

The current accepted checkpoint is:

- source tables: **5,631**;
- source rows: **138,036**;
- mapped rows: **138,036 / 138,036**;
- missing rows: **0**;
- changed translations: **120,932**;
- same Han-only rows (non-actionable in this coverage gate): **596**;
- same safe/non-Japanese rows: **16,508**;
- same-kana rows: **0**;
- translated rows with kana residue: **0**;
- actionable rows: **0**;
- maintained translation rows outside the current source universe: **5,149**.

The final 5,149 rows are reported as historical/extra translation data. They are not counted as missing current coverage.

## Why the generic QA does not compare every format token against this snapshot

The current `localizetext` resource and the maintained localized tables do not always use the same runtime representation.

For example, a current Japanese row may contain a concrete value such as `10秒` while the maintained localized row uses a runtime placeholder such as `{0}秒`. Similar intentional differences exist for line wrapping, NBSP, rich-text expansion, and numeric/template representation.

Therefore:

- `tools/audit_current_localizetext.py` is the authoritative **current 2.17 coverage and untranslated-kana gate**;
- `tools/qa.py` remains the broader compatibility/review layer for protected syntax, historical alignment, terminology, exact-source consistency, layout review, and source-key surfaces;
- the full current snapshot must **not** be blindly fed into old source/target signature-equality checks.

A difference is not safe to auto-edit merely because source and translation signatures differ.

## Agent/community use

The full snapshot is public input for:

- exact current source lookup by table/key;
- detecting source changes across client versions;
- building current-version Translation Memory;
- preparing contextual Agent review;
- deciding whether a historical backlog item is still relevant.

Agents should prefer the full current snapshot over historical `DumpData` whenever a `localify` table/key is involved.

The snapshot contains source text and public version/hash metadata only. It intentionally excludes personal paths, accounts, runtime logs, private endpoints, device state, and private integration details.

## Updating for a new client version

A version update should publish a new immutable source snapshot and manifest entry, then:

1. verify table/key uniqueness and deterministic hashes;
2. compare the new source universe with the previous supported snapshot;
3. audit maintained translations against the new universe;
4. distinguish new, deleted, unchanged, and source-changed table/key identities;
5. translate/review only the actual unresolved current rows;
6. update the public current-source coverage checkpoint;
7. retain older snapshots only when they remain useful for reproducibility/history.

Do not silently overwrite source provenance without updating the manifest and documentation.

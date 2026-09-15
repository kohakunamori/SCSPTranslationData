# Client Version Update Workflow

This workflow keeps existing translations while making source changes reviewable.

## 1. Acquire current source text

Prefer a dump from the current supported client. Use the repository `DumpData` branch as a historical/reference source, not an assumption that it is current.

For the currently supported 2.17.0 main text and current Drama surfaces, public authoritative source anchors are already bundled under `qa/current-source/`. See [current-source-snapshot.md](current-source-snapshot.md).

Collect all relevant surfaces:

- main localify tables;
- local2 exact-source strings;
- lyrics;
- current Drama consumer dialogue;
- scenario data.

## 2. Preserve stable identity

Align by the format's stable identity:

- `localify.json`: table + key;
- `local2.json`: source key;
- `lyrics.json`: source lyric key;
- `drama.json`: exact `uniqueId + source` runtime key; use the published collision-safe identity for review tooling;
- scenario: relative path + record key.

Do not infer identity from translated text.

## 3. Carry forward known translations

The existing helper can migrate `localify.json` by table/key:

```bash
cd scsp_localify
python update_local_json.py
```

This is a mechanical carry-forward step only. It does not prove that the Japanese source behind a stable key has not changed.

## 4. Classify changes

Separate at least:

- unchanged source with maintained translation;
- new key/source;
- deleted key/source;
- stable key whose source meaning changed;
- translation-memory conflict;
- intentionally same-form content.

Only unresolved/new/changed text should normally need fresh translation.

For a new supported client version, create a new immutable current-source snapshot and compare table/key identity against the previous snapshot. Do not silently overwrite the old source universe or infer source changes from translated text.

## 5. Translate with context

Use `qa/glossary.json`, `qa/names.json`, existing nearby translations, and generated translation memory.

For scenarios, keep adjacent dialogue in the review context.

## 6. Validate

Run:

```bash
python tools/qa.py
python tools/audit_current_localizetext.py
python tools/audit_current_drama.py
git diff --check
```

When `DumpData` is available locally, also inspect:

```bash
python tools/build_translation_memory.py
```

Treat hard errors as blockers. Review warnings according to their surface and context.

The current-localizetext audit is a separate hard coverage gate. It must show every current source row mapped and no current same-kana/translated-kana-residual actionable rows before the version update is considered source-complete.

The current-Drama audit is also a hard gate. A new client version must independently rebuild the Drama source universe, preserve the consumer selection rule, verify runtime-key uniqueness, and classify new/deleted/source-changed dialogue rows before carrying translations forward.

## 7. Submit a bounded PR

State:

- client/source version or provenance;
- affected surfaces;
- migration method;
- translation method;
- QA status;
- intentional exceptions.

Do not include game binaries, account/runtime captures, personal paths, credentials, or private infrastructure in the public update.

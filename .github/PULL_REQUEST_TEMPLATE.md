## Scope

Describe the affected surface(s), table(s), scenario(s), lyrics, or QA/tooling area.

## Source provenance

- [ ] Current source-key surface (`local2.json` / `lyrics.json`)
- [ ] Bundled current `localify` snapshot (`qa/current-source/`)
- [ ] Current client dump verified
- [ ] Historical `DumpData` reference only
- [ ] Not source-sensitive (docs/tooling only)

For `localify`, prefer the bundled current snapshot. If historical `DumpData` was used for source-sensitive changes, explain how the current source was verified.

## Translation method

- [ ] Human-authored/reviewed
- [ ] Agent-assisted and reviewed
- [ ] Mechanical migration
- [ ] QA/tooling/docs only

For Agent-assisted work, name the public batch/result workflow or describe the review method. Do not include private infrastructure details.

## QA

Run before submitting:

```bash
python -m unittest discover -s tools -p "test_*.py"
python tools/qa.py
python tools/audit_current_localizetext.py
python tools/canonicalize_exact_source_conflicts.py --check
python tools/build_quality_backlog.py --check-current-key
git diff --check
```

Report:

- Hard errors:
- Review warnings before:
- Review warnings after:
- Backlog tasks before:
- Backlog tasks after:
- Current-key blockers:
- Strict canonicalization candidates:
- Current localizetext mapped / missing / actionable:
- Relevant backlog IDs/categories:

## Review notes

Explain intentional warnings, terminology decisions, context-sensitive translations, or rendering/layout considerations.

## Public-repository privacy

- [ ] No account data, cookies, tokens, authorization headers, startup secrets, private endpoints, personal absolute paths, or private-project details are included.
- [ ] No unrelated game binaries/resources, logs, captures, or dumps are included.

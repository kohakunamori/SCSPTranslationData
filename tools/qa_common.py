from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scsp_localify"
QA = ROOT / "qa"

BRACE_RE = re.compile(r"\{[^{}]+\}")
PRINTF_RE = re.compile(r"%(?:\d+\$)?[-+#0 .'\d]*(?:\.\d+)?[A-Za-z%]")
TAG_RE = re.compile(r"<[^>]+>")
KANA_RE = re.compile(r"[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fd-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
DIGIT_RE = re.compile(r"\d+(?:\.\d+)?")
PERCENT_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*[%％]")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def git(*args: str, binary: bool = False) -> str | bytes:
    out = subprocess.check_output(["git", *args], cwd=ROOT)
    return out if binary else out.decode("utf-8-sig")


def ref_exists(ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def resolve_dump_ref(explicit: str | None = None) -> str | None:
    if explicit:
        if not ref_exists(explicit):
            raise ValueError(f"Dump ref does not exist: {explicit}")
        return explicit
    for ref in ("origin/DumpData", "DumpData"):
        if ref_exists(ref):
            return ref
    return None


def git_show_json(ref: str, path: str) -> Any:
    raw = git("show", f"{ref}:{path}")
    assert isinstance(raw, str)
    return json.loads(raw)


def archive_json_tree(ref: str, prefix: str) -> dict[str, Any]:
    raw = git("archive", "--format=tar", ref, prefix, binary=True)
    assert isinstance(raw, bytes)
    result: dict[str, Any] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            result[member.name] = json.loads(fh.read().decode("utf-8-sig"))
    return result


def has_kana(text: str) -> bool:
    return bool(KANA_RE.search(text))


def has_unpreserved_kana(text: str, preserve_terms: Iterable[str]) -> bool:
    remaining = text
    for term in preserve_terms:
        if term:
            variants = {
                term,
                term.replace(" ", "\u00a0"),
                term.replace("\u00a0", " "),
            }
            for variant in variants:
                remaining = remaining.replace(variant, "")
    return has_kana(remaining)


def has_han(text: str) -> bool:
    return bool(HAN_RE.search(text))


def compact_display_spacing(text: str) -> str:
    return text.replace(" ", "").replace("\u00a0", "").replace("\u3000", "")


def canonical_same_form(source: str, names: dict[str, Any]) -> bool:
    compact_source = compact_display_spacing(source)
    for row in names.get("names", []):
        if not isinstance(row, dict):
            continue
        name_source = row.get("source")
        translation = row.get("translation")
        if not isinstance(name_source, str) or not isinstance(translation, str):
            continue
        if compact_display_spacing(name_source) != compact_source:
            continue
        if compact_display_spacing(translation) == compact_source:
            return True
    return False


def format_signature(text: str) -> dict[str, Any]:
    return {
        "brace": dict(Counter(BRACE_RE.findall(text))),
        "printf": dict(Counter(PRINTF_RE.findall(text))),
        "tags": dict(Counter(TAG_RE.findall(text))),
        "lf": text.count("\n"),
        "cr": text.count("\r"),
        "nbsp": text.count("\u00a0"),
    }


def numeric_signature(text: str) -> Counter[str]:
    norm = unicodedata.normalize("NFKC", text)
    return Counter(DIGIT_RE.findall(norm))


def percentage_signature(text: str) -> Counter[str]:
    norm = unicodedata.normalize("NFKC", text)
    return Counter(PERCENT_RE.findall(norm))


def lyric_translation_only(source: str, target: str) -> str:
    if target == source:
        return ""
    for sep in ("\r\n", "\n"):
        prefix = source + sep
        if target.startswith(prefix):
            return target[len(prefix):]
    return target


def flatten_localify(data: Any) -> Iterable[tuple[str, str, str]]:
    if not isinstance(data, dict):
        return
    for table, entries in data.items():
        if not isinstance(entries, dict):
            continue
        for key, value in entries.items():
            if isinstance(value, str):
                yield str(table), str(key), value


def scenario_records(data: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        text = row.get("text")
        if isinstance(key, str) and isinstance(text, str):
            out[key] = text
    return out


def current_scenario_files() -> dict[str, Path]:
    base = DATA / "scenario"
    return {
        path.relative_to(DATA).as_posix(): path
        for path in base.rglob("*.json")
    }


def dump_scenario_data(ref: str) -> dict[str, Any]:
    tree = archive_json_tree(ref, "dumps/scenario")
    return {
        name.removeprefix("dumps/"): value
        for name, value in tree.items()
    }


def aligned_records(dump_ref: str | None) -> Iterable[dict[str, str]]:
    local2 = load_json(DATA / "local2.json")
    if isinstance(local2, dict):
        for source, target in local2.items():
            if isinstance(source, str) and isinstance(target, str):
                yield {
                    "surface": "local2",
                    "identity": source,
                    "source": source,
                    "translation": target,
                    "provenance": "current-source-key",
                }

    lyrics = load_json(DATA / "lyrics.json")
    if isinstance(lyrics, dict):
        for source, target in lyrics.items():
            if isinstance(source, str) and isinstance(target, str):
                yield {
                    "surface": "lyrics",
                    "identity": source,
                    "source": source,
                    "translation": target,
                    "provenance": "current-source-key",
                }

    if not dump_ref:
        return

    current_localify = load_json(DATA / "localify.json")
    source_localify = git_show_json(dump_ref, "dumps/localify.json")
    if isinstance(current_localify, dict) and isinstance(source_localify, dict):
        for table, source_entries in source_localify.items():
            target_entries = current_localify.get(table)
            if not isinstance(source_entries, dict) or not isinstance(target_entries, dict):
                continue
            for key, source in source_entries.items():
                target = target_entries.get(key)
                if isinstance(source, str) and isinstance(target, str):
                    yield {
                        "surface": "localify",
                        "identity": f"{table}:{key}",
                        "table": str(table),
                        "key": str(key),
                        "source": source,
                        "translation": target,
                        "provenance": f"{dump_ref}:dumps/localify.json",
                    }

    source_scenarios = dump_scenario_data(dump_ref)
    for rel, path in current_scenario_files().items():
        source_data = source_scenarios.get(rel)
        if source_data is None:
            continue
        target_data = load_json(path)
        source_rows = scenario_records(source_data)
        target_rows = scenario_records(target_data)
        for key, source in source_rows.items():
            target = target_rows.get(key)
            if isinstance(target, str):
                yield {
                    "surface": "scenario",
                    "identity": f"{rel}:{key}",
                    "path": rel,
                    "key": key,
                    "source": source,
                    "translation": target,
                    "provenance": f"{dump_ref}:dumps/{rel}",
                }


def load_policy() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_json(QA / "rules.json"),
        load_json(QA / "glossary.json"),
        load_json(QA / "names.json"),
        load_json(QA / "allowed-source-equal.json"),
    )

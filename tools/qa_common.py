from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scsp_localify"
QA = ROOT / "qa"
CURRENT_SOURCE = QA / "current-source"
LOCALIZETEXT_SOURCE_SNAPSHOT = CURRENT_SOURCE / "localizetext-2.17-source.json.gz"
LOCALIZETEXT_QA_SCOPE_SNAPSHOT = CURRENT_SOURCE / "localizetext-2.17-qa-scope.json.gz"
LOCALIZETEXT_SOURCE_MANIFEST = CURRENT_SOURCE / "manifest.json"

BRACE_RE = re.compile(r"\{[^{}]+\}")
PRINTF_RE = re.compile(r"%(?:\d+\$)?[-+#0 .'\d]*(?:\.\d+)?[A-Za-z%]")
TAG_RE = re.compile(r"<[^>]+>")
KANA_RE = re.compile(r"[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fd-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
DIGIT_RE = re.compile(r"\d+(?:\.\d+)?")
PERCENT_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*[%％]")
CJK_COUNT_RE = re.compile(
    r"第?([零〇一二三四五六七八九十百千万两兩]+)"
    r"(?=(?:人|名|次|回|行|季|章|話|话|倍|個|个|枚|件|張|张|首|天|日|年|月|分|秒))"
)
CJK_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CJK_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_current_localizetext_source() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not LOCALIZETEXT_SOURCE_SNAPSHOT.exists() or not LOCALIZETEXT_SOURCE_MANIFEST.exists():
        return None, None

    manifest = load_json(LOCALIZETEXT_SOURCE_MANIFEST)
    if not isinstance(manifest, dict):
        raise ValueError("current-source manifest must be a JSON object")

    compressed = LOCALIZETEXT_SOURCE_SNAPSHOT.read_bytes()
    expected_gzip_hash = manifest.get("gzip_sha256")
    actual_gzip_hash = hashlib.sha256(compressed).hexdigest()
    if isinstance(expected_gzip_hash, str) and actual_gzip_hash != expected_gzip_hash:
        raise ValueError(
            f"current-source gzip hash mismatch: expected {expected_gzip_hash}, got {actual_gzip_hash}"
        )

    raw = gzip.decompress(compressed)
    expected_raw_hash = manifest.get("uncompressed_sha256")
    actual_raw_hash = hashlib.sha256(raw).hexdigest()
    if isinstance(expected_raw_hash, str) and actual_raw_hash != expected_raw_hash:
        raise ValueError(
            f"current-source raw hash mismatch: expected {expected_raw_hash}, got {actual_raw_hash}"
        )

    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("current-source localizetext snapshot must be a JSON object")
    tables = len(data)
    rows = sum(len(value) for value in data.values() if isinstance(value, dict))
    if manifest.get("tables") != tables or manifest.get("rows") != rows:
        raise ValueError(
            "current-source manifest count mismatch: "
            f"manifest={manifest.get('tables')} tables/{manifest.get('rows')} rows, "
            f"snapshot={tables} tables/{rows} rows"
        )
    return data, manifest


@lru_cache(maxsize=1)
def load_current_localizetext_qa_scope() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not LOCALIZETEXT_QA_SCOPE_SNAPSHOT.exists() or not LOCALIZETEXT_SOURCE_MANIFEST.exists():
        return None, None

    manifest = load_json(LOCALIZETEXT_SOURCE_MANIFEST)
    scope_meta = manifest.get("qa_scope") if isinstance(manifest, dict) else None
    if not isinstance(scope_meta, dict):
        raise ValueError("current-source manifest is missing qa_scope metadata")

    compressed = LOCALIZETEXT_QA_SCOPE_SNAPSHOT.read_bytes()
    expected_gzip_hash = scope_meta.get("gzip_sha256")
    actual_gzip_hash = hashlib.sha256(compressed).hexdigest()
    if isinstance(expected_gzip_hash, str) and actual_gzip_hash != expected_gzip_hash:
        raise ValueError(
            f"current-source QA scope gzip hash mismatch: expected {expected_gzip_hash}, got {actual_gzip_hash}"
        )

    raw = gzip.decompress(compressed)
    expected_raw_hash = scope_meta.get("uncompressed_sha256")
    actual_raw_hash = hashlib.sha256(raw).hexdigest()
    if isinstance(expected_raw_hash, str) and actual_raw_hash != expected_raw_hash:
        raise ValueError(
            f"current-source QA scope raw hash mismatch: expected {expected_raw_hash}, got {actual_raw_hash}"
        )

    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("current-source localizetext QA scope must be a JSON object")
    tables = len(data)
    rows = sum(len(value) for value in data.values() if isinstance(value, dict))
    if scope_meta.get("tables") != tables or scope_meta.get("rows") != rows:
        raise ValueError(
            "current-source QA scope count mismatch: "
            f"manifest={scope_meta.get('tables')} tables/{scope_meta.get('rows')} rows, "
            f"snapshot={tables} tables/{rows} rows"
        )
    return data, scope_meta


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


def parse_cjk_number(token: str) -> int | None:
    if not token:
        return None
    if not any(char in CJK_UNITS for char in token):
        digits = []
        for char in token:
            value = CJK_DIGITS.get(char)
            if value is None:
                return None
            digits.append(str(value))
        return int("".join(digits)) if digits else None

    result = 0
    section = 0
    number = 0
    for char in token:
        if char in CJK_DIGITS:
            number = CJK_DIGITS[char]
            continue
        unit = CJK_UNITS.get(char)
        if unit is None:
            return None
        if unit == 10000:
            section += number
            result += section * unit
            section = 0
            number = 0
            continue
        if number == 0:
            number = 1
        section += number * unit
        number = 0
    return result + section + number


def numeric_signature(text: str) -> Counter[str]:
    norm = unicodedata.normalize("NFKC", text)
    return Counter(DIGIT_RE.findall(norm))


def cjk_numeric_signature(text: str) -> Counter[str]:
    norm = unicodedata.normalize("NFKC", text)
    signature: Counter[str] = Counter()
    for match in CJK_COUNT_RE.finditer(norm):
        value = parse_cjk_number(match.group(1))
        if value is not None:
            signature[str(value)] += 1
    signature["2"] += norm.count("翻倍")
    return signature


def numeric_signatures_match(source: str, target: str) -> bool:
    source_sig = numeric_signature(source)
    target_sig = numeric_signature(target)
    if source_sig == target_sig:
        return True

    # Preserve the original detector's behavior when the source carries no
    # explicit Arabic/full-width numeric tokens. CJK numerals in natural
    # Chinese text such as "上一个" must not create new false positives.
    if not source_sig:
        return False

    # Target-side Chinese numerals may be a natural rendering of a numeric
    # source token (4 -> 四名, 2 -> 两行, 1 -> 第一季, 10 -> 十次,
    # 2倍 -> 翻倍). Use them only to fill deficits from the explicit source
    # signature; unused CJK numerals are ignored.
    target_cjk = cjk_numeric_signature(target)
    remaining = source_sig.copy()
    for value, count in target_sig.items():
        remaining[value] -= count
        if remaining[value] < 0:
            return False
    for value in list(remaining):
        if remaining[value] <= 0:
            del remaining[value]
            continue
        fill = min(remaining[value], target_cjk[value])
        remaining[value] -= fill
        if remaining[value] <= 0:
            del remaining[value]
    return not remaining


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


def reviewed_semantic_exception(
    rules: dict[str, Any],
    code: str,
    surface: str,
    source: str,
    translation: str,
) -> bool:
    for row in rules.get("reviewed_semantic_exceptions", []):
        if not isinstance(row, dict):
            continue
        if (
            row.get("code") == code
            and row.get("surface") == surface
            and row.get("source") == source
            and row.get("translation") == translation
        ):
            return True
    return False

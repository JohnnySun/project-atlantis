from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("m2_glossary_audit", HERE / "m2_glossary_audit.py")
assert SPEC and SPEC.loader
m2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m2)


HEADER = "\t".join(m2.HEADER)


def source_row(string_id: int, text: str) -> str:
    return json.dumps(
        {"string_id": string_id, "locale": "ja", "text": text},
        ensure_ascii=False,
    )


def glossary_row(
    *,
    key: str = "unit.alpha",
    target: str = "阿爾法",
    status: str = "accepted",
    source_id: int = 1,
    source_hash: str | None = None,
    urls: str = "https://example.com/a;https://example.com/b",
    candidates: str = "",
) -> str:
    source_hash = source_hash or hashlib.sha256(b"AB").hexdigest()
    values = [
        key,
        target,
        "unit",
        status,
        str(source_id),
        source_hash,
        urls,
        candidates,
        "bounded test provenance",
    ]
    return "\t".join(values)


class M2GlossaryAuditTests(unittest.TestCase):
    def write_fixture(self, glossary: str, source: str):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        glossary_path = root / "glossary.tsv"
        source_path = root / "source.jsonl"
        glossary_path.write_text(glossary, encoding="utf-8")
        source_path.write_text(source, encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return glossary_path, source_path

    def test_real_glossary_is_source_safe_and_hashes_match(self) -> None:
        glossary = HERE.parent / "translations" / "glossary.zh-TW.tsv"
        source = HERE.parent / "research" / "super-robot-taisen-d-decoded.jsonl"
        report = m2.audit(glossary, source)
        self.assertGreater(report["glossary_entries"], 0)
        self.assertEqual(report["source_text_emitted"], False)
        self.assertTrue(report["deferred_terms_fail_closed"])

    def test_accepts_hash_checked_entry(self) -> None:
        glossary, source = self.write_fixture(
            HEADER + "\n" + glossary_row() + "\n",
            source_row(1, "AB") + "\n",
        )
        report = m2.audit(glossary, source)
        self.assertEqual(report["source_hash_matches"], 1)

    def test_deferred_conflict_must_not_allocate_target(self) -> None:
        glossary, source = self.write_fixture(
            HEADER
            + "\n"
            + glossary_row(
                target="",
                status="deferred_conflict",
                candidates="甲/乙",
            )
            + "\n",
            source_row(1, "AB") + "\n",
        )
        report = m2.audit(glossary, source)
        self.assertEqual(report["status_counts"], {"deferred_conflict": 1})

    def test_rejects_source_hash_mismatch(self) -> None:
        glossary, source = self.write_fixture(
            HEADER + "\n" + glossary_row(source_hash="0" * 64) + "\n",
            source_row(1, "AB") + "\n",
        )
        with self.assertRaisesRegex(m2.GlossaryAuditError, "source hash mismatch"):
            m2.audit(glossary, source)

    def test_rejects_kana_leak_and_single_source(self) -> None:
        kana_glossary, source = self.write_fixture(
            HEADER + "\n" + glossary_row(target="阿カ") + "\n",
            source_row(1, "AB") + "\n",
        )
        with self.assertRaisesRegex(m2.GlossaryAuditError, "kana"):
            m2.audit(kana_glossary, source)

        one_source_glossary, source = self.write_fixture(
            HEADER
            + "\n"
            + glossary_row(urls="https://example.com/only")
            + "\n",
            source_row(1, "AB") + "\n",
        )
        with self.assertRaisesRegex(m2.GlossaryAuditError, "two sources"):
            m2.audit(one_source_glossary, source)


if __name__ == "__main__":
    unittest.main()

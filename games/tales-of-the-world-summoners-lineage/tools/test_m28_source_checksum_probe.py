import hashlib
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m28_source_checksum_probe import audit_rows  # noqa: E402


def row(text: str, *, row_id: str = "synthetic") -> dict[str, object]:
    return {
        "string_id": row_id,
        "locale": "ja",
        "text": text,
        "source_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "provenance": "synthetic-test;decoder=test",
        "decoder_version": "test",
        "runtime_context": False,
        "scene_role": "unclassified",
        "eligible_for_ledger": False,
    }


class M28SourceChecksumProbeTests(unittest.TestCase):
    def test_local_candidate_hashes_pass_but_ledger_gate_stays_closed(self) -> None:
        result = audit_rows([row("synthetic")])
        self.assertEqual(result["source_hash_mismatch_count"], 0)
        self.assertTrue(result["ledger_gate"]["schema_complete"])
        self.assertFalse(result["ledger_gate"]["open"])
        self.assertFalse(result["source_text_emitted"])

    def test_hash_drift_and_duplicate_id_are_reported(self) -> None:
        first = row("one", row_id="same")
        second = row("two", row_id="same")
        second["source_text_sha256"] = "0" * 64
        result = audit_rows([first, second])
        self.assertEqual(result["source_hash_mismatch_count"], 1)
        self.assertEqual(result["duplicate_id_count"], 1)
        self.assertFalse(result["ledger_gate"]["open"])

    def test_required_fields_are_counted(self) -> None:
        result = audit_rows([{"string_id": "short"}])
        self.assertGreater(result["required_field_missing_counts"]["text"], 0)
        self.assertFalse(result["ledger_gate"]["schema_complete"])


if __name__ == "__main__":
    unittest.main()

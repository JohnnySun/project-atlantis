import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m18_narrow_allocator import emit_seed_ledger


ROOT = Path(__file__).resolve().parents[1]


class M4UIBatch3MetadataTest(unittest.TestCase):
    def test_seed_uses_verified_source_shape_width(self) -> None:
        # Escaped codepoints keep the synthetic source out of the tracked file
        # as readable Japanese text while exercising three narrow units.
        source_text = "".join(chr(codepoint) for codepoint in (0x30BF, 0x30A4, 0x30D7))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample-decoded.jsonl"
            output = Path(directory) / "seed.jsonl"
            source.write_text(
                json.dumps({"string_id": 0x100, "text": source_text}, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            emit_seed_ledger(source, 0x100, output)
            row = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(row["context"]["max_width"], 24)
        self.assertEqual(row["context"]["max_lines"], 1)
        self.assertEqual(row["context"]["control_codes"], [])

    def test_batch_report_is_source_safe_and_static_only(self) -> None:
        report = json.loads((ROOT / "research/m4-ui-batch3.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["selection"]["record_count"], 5)
        self.assertEqual(report["selection"]["line_width"], 24)
        self.assertEqual(report["selection"]["control_token_count"], 0)
        self.assertTrue(report["roundtrip"]["rom_outside_allowed_ranges_equal"])
        self.assertFalse(report["gate"]["runtime_screen_verified"])

    def test_tracked_ledger_has_only_source_safe_rows(self) -> None:
        path = ROOT / "translations/m4-ui-batch-3.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 5)
        self.assertEqual({row["string_id"] for row in rows}, {512252, 512308, 513780, 516716, 517320})
        for row in rows:
            self.assertNotIn("source", row)
            self.assertEqual(row["status"], "ai_draft")
            self.assertEqual(len(row["source_hash"]), 64)
            self.assertEqual(row["context"]["max_width"], 24)


if __name__ == "__main__":
    unittest.main()

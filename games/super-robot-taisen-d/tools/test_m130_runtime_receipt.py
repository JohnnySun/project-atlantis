from __future__ import annotations

import json
import unittest
from pathlib import Path

from m130_runtime_receipt import RuntimeReceiptReject, source_safe


ROOT = Path(__file__).resolve().parents[1]


class M130RuntimeReceiptTest(unittest.TestCase):
    def test_tracked_receipt_is_source_safe_and_fail_closed(self) -> None:
        receipt = json.loads(
            (ROOT / "research/m130-corrected-runtime-receipt.json").read_text(encoding="utf-8")
        )
        source_safe(receipt)
        self.assertEqual(receipt["runtime"]["target"]["string_id"], 526424)
        self.assertTrue(receipt["gate"]["target_layout_and_render_exact"])
        self.assertFalse(receipt["gate"]["natural_screen_proven"])
        self.assertFalse(receipt["gate"]["release_ready"])

    def test_forbidden_raw_or_text_keys_reject(self) -> None:
        with self.assertRaisesRegex(RuntimeReceiptReject, "forbidden_key"):
            source_safe({"text": "forbidden"})
        with self.assertRaisesRegex(RuntimeReceiptReject, "forbidden_key"):
            source_safe({"pixels": [1, 2, 3]})


if __name__ == "__main__":
    unittest.main()

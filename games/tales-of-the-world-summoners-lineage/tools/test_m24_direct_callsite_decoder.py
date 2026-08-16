import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m24_direct_callsite_decoder import (  # noqa: E402
    DECODER_VERSION,
    stable_direct_candidate_id,
    summary,
)


class M24DirectCallsiteDecoderTests(unittest.TestCase):
    def test_candidate_id_is_stable_and_callsite_scoped(self) -> None:
        first = stable_direct_candidate_id(0x08015E92 - 0x08000000, 0x1FA616, 40)
        same = stable_direct_candidate_id(0x08015E92 - 0x08000000, 0x1FA616, 40)
        other = stable_direct_candidate_id(0x08015EA6 - 0x08000000, 0x1FA616, 40)
        self.assertEqual(first, same)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 24)

    def test_summary_keeps_runtime_and_ledger_gates_closed(self) -> None:
        data = b"rom"
        rows = [
            {
                "complete_codepage": False,
                "unresolved_code_units": ["0x1234"],
                "control_candidates": ["0xFF70"],
                "stream_file_offset": "0x100",
            }
        ]
        result = summary(data, rows)
        self.assertEqual(result["decoder_version"], DECODER_VERSION)
        self.assertFalse(result["runtime_context_confirmed"])
        self.assertFalse(result["eligible_for_ledger"])
        self.assertEqual(result["distinct_unresolved_code_units"], 1)
        self.assertNotIn("text", result)


if __name__ == "__main__":
    unittest.main()

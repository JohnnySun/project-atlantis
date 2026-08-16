import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m22_control_code_probe import (  # noqa: E402
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    classify_unit,
    stream_unit_counts,
)


def packed(*units: int) -> bytes:
    return b"".join(unit.to_bytes(2, "little") for unit in units)


class M22ControlCodeProbeTests(unittest.TestCase):
    def test_bounded_stream_counts_parser_candidates_without_units(self) -> None:
        profile = stream_unit_counts(
            packed(0x005E, LINE_ADVANCE_CODE_UNIT, 0x0001, NULL_CODE_UNIT, 0x0066),
            0,
            max_units=16,
        )
        self.assertEqual(profile["unit_count_including_terminator"], 4)
        self.assertTrue(profile["terminated_by_0000"])
        self.assertEqual(profile["line_advance_count"], 1)
        self.assertEqual(profile["blank_record_candidate_count"], 1)
        self.assertNotIn("units", profile)
        self.assertNotIn("text", profile)

    def test_cap_is_reported_as_non_terminated(self) -> None:
        profile = stream_unit_counts(packed(0x005E, 0x0066), 0, max_units=1)
        self.assertFalse(profile["terminated_by_0000"])
        self.assertTrue(profile["capped_or_truncated"])

    def test_parser_classification_keeps_semantics_separate(self) -> None:
        class FakeRom(bytes):
            pass

        # No supplied record bytes means the non-special unit remains a normal
        # record-index candidate; the probe must not infer a control meaning.
        fake = FakeRom(b"\0" * 0x100)
        self.assertEqual(classify_unit(fake, NULL_CODE_UNIT), "parser-terminator-0000")
        self.assertEqual(classify_unit(fake, LINE_ADVANCE_CODE_UNIT), "parser-special-ff70-candidate")
        self.assertEqual(classify_unit(fake, 0x005E), "font-record-index")


if __name__ == "__main__":
    unittest.main()

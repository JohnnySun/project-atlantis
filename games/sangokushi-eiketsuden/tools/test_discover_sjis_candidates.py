import importlib.util
import pathlib
import struct
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("discover_sjis_candidates.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_discover_sjis", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load discover_sjis_candidates.py")
DISCOVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISCOVER)


class DiscoverSjisCandidatesTest(unittest.TestCase):
    def test_pointer_referenced_record_reports_metadata_without_text(self) -> None:
        data = bytearray(0x300)
        target = 0x180
        data[target : target + 9] = "劉備援軍".encode("shift_jis") + b"\0"
        struct.pack_into("<I", data, 0x20, DISCOVER.ROM_BASE + target)

        rows = DISCOVER.discover(bytes(data), exclude_known=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target_file_offset"], "0x000180")
        self.assertEqual(rows[0]["pointer_reference_count"], 1)
        self.assertNotIn("text", rows[0])
        self.assertEqual(rows[0]["terminator"], "0x00")

    def test_known_target_window_can_be_excluded(self) -> None:
        data = bytearray(0x80000)
        target = 0x075A80
        data[target : target + 9] = "劉備援軍".encode("shift_jis") + b"\0"
        struct.pack_into("<I", data, 0x20, DISCOVER.ROM_BASE + target)

        self.assertEqual(DISCOVER.discover(bytes(data)), [])
        self.assertEqual(len(DISCOVER.discover(bytes(data), exclude_known=False)), 1)

    def test_control_bytes_and_short_payloads_are_rejected(self) -> None:
        data = bytearray(0x300)
        short_target = 0x100
        control_target = 0x140
        data[short_target : short_target + 4] = "劉備".encode("shift_jis") + b"\0"
        data[control_target : control_target + 10] = b"\x01" + "劉備援軍".encode("shift_jis") + b"\0"
        struct.pack_into("<I", data, 0x20, DISCOVER.ROM_BASE + short_target)
        struct.pack_into("<I", data, 0x24, DISCOVER.ROM_BASE + control_target)

        self.assertEqual(DISCOVER.discover(bytes(data), exclude_known=False), [])


if __name__ == "__main__":
    unittest.main()

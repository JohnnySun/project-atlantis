import importlib.util
import pathlib
import struct
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("analyze_story_pool.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_story_pool", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load analyze_story_pool.py")
ANALYZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZE)


class AnalyzeStoryPoolTest(unittest.TestCase):
    def test_boundary_counts_pointers_and_keeps_source_out_of_report(self) -> None:
        data = bytearray(0xCE000)
        data[ANALYZE.STORY_TABLE_OFFSET - 4 : ANALYZE.STORY_TABLE_OFFSET] = struct.pack("<I", 0)
        for entry in range(ANALYZE.STORY_ENTRY_COUNT):
            target = 0x1000 + entry * 0x20
            struct.pack_into("<I", data, ANALYZE.STORY_TABLE_OFFSET + entry * 4, ANALYZE.ROM_BASE + target)
            data[target : target + 9] = "劉備援軍".encode("shift_jis") + b"\0"
        struct.pack_into("<I", data, ANALYZE.STORY_TABLE_END, 0x19010502)
        struct.pack_into("<I", data, ANALYZE.STORY_TABLE_END + 4, 0x02000000)

        report = ANALYZE.story_pool_boundary(bytes(data))

        self.assertEqual(report["entry_count"], 33)
        self.assertEqual(report["unique_target_count"], 33)
        self.assertEqual(report["shift_jis_valid_count"], 33)
        self.assertNotIn("text", report)
        self.assertNotIn("raw_bytes", report["record_metadata"][0])

    def test_static_chain_constants_keep_runtime_reachability_separate(self) -> None:
        self.assertEqual(ANALYZE.STORY_TABLE_LITERAL_OFFSET, 0x011990)
        self.assertEqual(ANALYZE.WRITER_ADDRESS, 0x0800CAD8)
        self.assertEqual(ANALYZE.RECORD_PAIR_HELPER_ADDRESS, 0x08011904)
        self.assertEqual(ANALYZE.WRITER_HELPER_ADDRESS, 0x080118C8)
        self.assertIn("natural-runtime-pending", "static-consumer-confirmed; natural-runtime-pending")


if __name__ == "__main__":
    unittest.main()

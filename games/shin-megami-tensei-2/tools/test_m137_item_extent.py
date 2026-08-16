import importlib.util
import json
from pathlib import Path
import unittest


TOOLS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("m137_item_extent", TOOLS / "m137_item_extent.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class M137ItemExtentTests(unittest.TestCase):
    def test_short_input_fails_closed(self):
        report = MODULE.static_report(b"\0" * 64)
        self.assertFalse(report["extent_contract"]["all_records_available"])
        self.assertEqual(report["identity_crosscheck"]["identity_status"], "unconfirmed")
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_full_contract_is_bounded_and_reversible(self):
        report = MODULE.static_report(bytes(range(256)) * 0x10000)
        scope = report["scan_scope"]
        extent = report["extent_contract"]
        self.assertFalse(scope["full_rom_string_scan"])
        self.assertFalse(scope["full_rom_glyph_scan"])
        self.assertFalse(scope["raw_units_emitted"])
        self.assertEqual(scope["record_count"], 0xD0)
        self.assertEqual(scope["record_stride"], 0x24)
        self.assertTrue(extent["field_copy_is_reversible"])
        self.assertFalse(extent["complete_codepage"])

    def test_record_report_never_contains_source_payload_fields(self):
        report = MODULE.static_report(b"\0" * (0x200000))
        forbidden = {"source", "text", "decoded_text", "units", "unit_values", "glyph_bytes"}
        for record in report["records"]:
            self.assertTrue(forbidden.isdisjoint(record))
            self.assertFalse(record["raw_field_emitted"])
            self.assertFalse(record["raw_units_emitted"])
            self.assertFalse(record["decoded_text_emitted"])

    def test_report_is_json_serializable(self):
        report = MODULE.static_report(b"\0" * (0x200000))
        json.dumps(report, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main()

import unittest

import verify_raw_span_identity as module


class RawSpanIdentityTest(unittest.TestCase):
    def test_token_encoder_reconstructs_mixed_byte_span(self) -> None:
        data = bytes((0x92, 0x34, 0xE1, 0xFF, 0xDF, 0x9B))
        records = [
            {
                "pointer_file": "0x000000",
                "span_end_file": "0x000006",
                "raw_hex": data.hex(),
                "tokens": [
                    {"kind": "pair", "lead": 0x92, "trail": 0x34},
                    {"kind": "alt-glyph", "lead": 0xE1, "value": 0xFF},
                    {"kind": "control-candidate", "value": 0xDF},
                    {"kind": "single-byte-candidate", "value": 0x9B},
                ],
            }
        ]
        report = module.verify_records(data, records)
        self.assertEqual(report["token_record_count"], 1)
        self.assertEqual(report["token_reencode_bytes"], 6)
        self.assertEqual(report["token_reencode_mismatches"], 0)
        self.assertEqual(report["token_encoder"], "proven")

    def test_replays_exact_non_overlapping_raw_spans(self) -> None:
        data = bytes(range(32))
        records = [
            {"pointer_file": "0x000004", "span_end_file": "0x000008", "raw_hex": data[4:8].hex()},
            {"pointer_file": "0x000010", "span_end_file": "0x000014", "raw_hex": data[16:20].hex()},
        ]
        report = module.verify_records(data, records)
        self.assertEqual(report["record_count"], 2)
        self.assertEqual(report["unique_pointer_count"], 2)
        self.assertEqual(report["covered_byte_count"], 8)
        self.assertEqual(report["changed_byte_count"], 0)

    def test_rejects_raw_span_drift(self) -> None:
        data = bytes(range(16))
        records = [{"pointer_file": "0x000004", "span_end_file": "0x000008", "raw_hex": "00010203"}]
        with self.assertRaises(ValueError):
            module.verify_records(data, records)

    def test_rejects_span_length_mismatch(self) -> None:
        data = bytes(range(16))
        records = [{"pointer_file": "0x000004", "span_end_file": "0x000009", "raw_hex": data[4:8].hex()}]
        with self.assertRaises(ValueError):
            module.verify_records(data, records)


if __name__ == "__main__":
    unittest.main()

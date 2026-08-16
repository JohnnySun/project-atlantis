import unittest

import verify_raw_span_identity as module


class RawSpanIdentityTest(unittest.TestCase):
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

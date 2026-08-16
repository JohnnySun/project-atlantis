#!/usr/bin/env python3
"""Tests for the source-separated, metadata-only B3TJ ledger scaffold."""

import hashlib
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import ledger_metadata  # noqa: E402


class LedgerMetadataTests(unittest.TestCase):
    def test_hash_matches_core_ledger_example(self):
        self.assertEqual(
            ledger_metadata.source_hash("＜原案＞"),
            "51b3add443562b99a9b1562dcbedd2251a12881bcfc05553d619c30638400ca4",
        )

    def test_build_removes_source_and_keeps_control_metadata(self):
        source = {
            "string_id": "sjis:0x1497E0",
            "locale": "ja",
            "text": "かな\n{12}%0t%k",
            "decoder_version": ledger_metadata.DECODER_VERSION,
            "region": "text-pool",
            "raw_length": 12,
        }
        safe, metadata = ledger_metadata.ledger_record(
            source, decoder_version=ledger_metadata.DECODER_VERSION
        )
        self.assertNotIn("source", safe)
        self.assertNotIn("text", safe)
        self.assertEqual(safe["targets"]["zh-TW"], {"text": ""})
        self.assertEqual(safe["context"]["control_codes"], ["%0t", "%k", "{12}"])
        self.assertEqual(metadata["newline_count"], 1)
        self.assertEqual(metadata["control_tokens"], {"%0t": 1, "%k": 1, "{12}": 1})

    def test_duplicate_or_decoder_drift_is_rejected(self):
        source = {
            "string_id": "sjis:0x100000",
            "locale": "ja",
            "text": "かな",
            "decoder_version": ledger_metadata.DECODER_VERSION,
            "region": "kana-and-names",
            "raw_length": 4,
        }
        with self.assertRaises(ledger_metadata.LedgerError):
            ledger_metadata.build_records([source, dict(source)])
        drifted = dict(source, decoder_version="other-decoder")
        with self.assertRaises(ledger_metadata.LedgerError):
            ledger_metadata.build_records([drifted])

    def test_verify_detects_hash_drift_without_printing_source(self):
        source = {
            "string_id": "sjis:0x100000",
            "locale": "ja",
            "text": "かな",
            "decoder_version": ledger_metadata.DECODER_VERSION,
            "region": "kana-and-names",
            "raw_length": 4,
        }
        ledger, _ = ledger_metadata.build_records([source])
        changed = json.loads(json.dumps(ledger[0]))
        changed["source_hash"] = hashlib.sha256("別".encode()).hexdigest()
        with self.assertRaises(ledger_metadata.LedgerError):
            ledger_metadata.verify_ledger([source], [changed])


if __name__ == "__main__":
    unittest.main()

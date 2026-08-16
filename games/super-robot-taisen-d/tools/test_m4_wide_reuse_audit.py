import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_wide_reuse_audit import WideReuseError, collect_source_identities, hash_ints


class M4WideReuseAuditTests(unittest.TestCase):
    def test_collects_identity_from_strict_source_context(self) -> None:
        rows = [{"offset": 0x100, "text": "移"}, {"offset": 0x200, "text": "移"}]
        identities = collect_source_identities(rows)
        self.assertEqual(len(identities), 1)
        identity = next(iter(identities.values()))
        self.assertEqual(identity["code_unit"], 0xDA88)
        self.assertEqual(identity["occurrence_count"], 2)
        self.assertEqual(identity["record_count"], 2)
        self.assertEqual(identity["runtime_status"], "runtime_confirmed_bounded")

    def test_repeated_context_deduplicates_without_losing_identity(self) -> None:
        rows = [{"offset": 0x100, "text": "移"}]
        identities = collect_source_identities(rows)
        self.assertEqual(sorted(identities), [(0x79FB, 0xDA88)])

    def test_hash_ints_is_source_safe(self) -> None:
        self.assertEqual(
            hash_ints([0x100, 0x200]),
            "6e0bb88def110121b47bdd39214a71a4476818bfbe96db963b98d90a033d62bf",
        )

    def test_bad_source_encoding_fails_closed(self) -> None:
        with self.assertRaises(WideReuseError):
            collect_source_identities([{"offset": 0x100, "text": "\ud800"}])


if __name__ == "__main__":
    unittest.main()

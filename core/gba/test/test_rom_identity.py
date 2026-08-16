from __future__ import annotations

import unittest

from core.gba.rom_identity import RomIdentityError, header_complement, inspect_bytes, verify_identity


def fixture(*, game_code: bytes = b"TEST", maker_code: bytes = b"01") -> bytes:
    data = bytearray(0x200)
    data[0xA0:0xAC] = b"ATLANTIS\0\0\0\0"
    data[0xAC:0xB0] = game_code
    data[0xB0:0xB2] = maker_code
    data[0xB2] = 0x96
    data[0xBC] = 3
    data[0xBD] = header_complement(data)
    return bytes(data)


class RomIdentityTest(unittest.TestCase):
    def test_header_complement_uses_negative_0x19_formula(self) -> None:
        data = bytearray(fixture())
        self.assertEqual(header_complement(data), (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF)
        self.assertNotEqual(header_complement(data), (0x19 - sum(data[0xA0:0xBD])) & 0xFF)

    def test_inspection_is_metadata_only_and_validates_header(self) -> None:
        identity = inspect_bytes(fixture(game_code=b"A6SJ", maker_code=b"D9"))
        self.assertEqual(identity["header"]["game_code"], "A6SJ")
        self.assertEqual(identity["header"]["maker_code"], "D9")
        self.assertTrue(identity["header"]["complement_valid"])
        self.assertNotIn("bytes", identity)
        self.assertNotIn("raw", identity["header"])

    def test_verification_fails_closed_on_mismatch(self) -> None:
        identity = inspect_bytes(fixture())
        diagnostics = verify_identity(identity, {"game_code": "NOPE", "size": 0x200})
        self.assertEqual([item["status"] for item in diagnostics], ["pass", "fail", "pass"])

    def test_unknown_expected_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(RomIdentityError, "unknown expected identity fields"):
            verify_identity(inspect_bytes(fixture()), {"sha_256": "typo"})

    def test_short_rom_is_unknown_not_partial_identity(self) -> None:
        with self.assertRaisesRegex(RomIdentityError, "shorter"):
            inspect_bytes(b"short")


if __name__ == "__main__":
    unittest.main()

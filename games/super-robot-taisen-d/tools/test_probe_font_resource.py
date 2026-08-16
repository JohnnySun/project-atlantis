#!/usr/bin/env python3
"""Pure tests for the bounded M1.6 font probe."""

from __future__ import annotations

import struct
import unittest

from probe_font_resource import (
    NARROW_SLOT,
    RESOURCE_DESCRIPTOR,
    RESOURCE_TABLE,
    ROM_BASE,
    WIDE_SLOT,
    code_unit_identities,
    gdb_pc_argument,
    identity_metadata,
    sha256,
    source_metadata,
    source_record_summary,
    static_resource_metadata,
    summarize_bytes,
    write_bounded_memory,
)


class FontProbeTest(unittest.TestCase):
    def test_bounded_memory_write_uses_small_chunks(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.writes = []

            def write_memory(self, address: int, data: bytes) -> None:
                self.writes.append((address, data))

        client = FakeClient()
        write_bounded_memory(client, 0x02019010, bytes(0x201))
        self.assertEqual(len(client.writes), 5)
        self.assertLessEqual(max(len(data) for _, data in client.writes), 0x80)
        self.assertEqual(client.writes[-1][0], 0x02019210)

    def test_gdb_pc_argument_accounts_for_prefetch_width(self) -> None:
        self.assertEqual(gdb_pc_argument(0x08000210, "arm"), 0x0800020C)
        self.assertEqual(gdb_pc_argument(0x08008724, "thumb"), 0x08008722)

    def test_static_resources_resolve_descriptor_entries(self) -> None:
        data = bytearray(0x120000)
        struct.pack_into("<I", data, RESOURCE_TABLE - ROM_BASE, RESOURCE_DESCRIPTOR)
        struct.pack_into("<I", data, RESOURCE_DESCRIPTOR - ROM_BASE + 2 * 4, 0x7704)
        struct.pack_into("<I", data, RESOURCE_DESCRIPTOR - ROM_BASE + 3 * 4, 0x35FAC)
        result = static_resource_metadata(bytes(data))
        self.assertEqual(result["narrow"]["resource_pointer"], "0x0814F664")
        self.assertEqual(result["wide"]["resource_pointer"], "0x08120DBC")
        self.assertEqual(result["narrow"]["slot"], f"0x{NARROW_SLOT:08X}")
        self.assertEqual(result["wide"]["slot"], f"0x{WIDE_SLOT:08X}")

    def test_strict_code_unit_and_identity_are_little_endian(self) -> None:
        rows = code_unit_identities("ラ")
        self.assertEqual(rows[0]["code_unit"], "0x8983")
        self.assertEqual(rows[0]["source_bytes"], "8389")
        identity = identity_metadata({"source_offset": "0x0007B3FC", **rows[0]})
        self.assertEqual(identity["unicode"], "ラ")
        self.assertNotIn("source_bytes", identity)

    def test_source_summary_omits_complete_code_units(self) -> None:
        metadata = source_metadata({"offset": 0x7B3FC, "text": "ラド"})
        summary = source_record_summary(metadata)
        self.assertEqual(summary["string_id"], "0x0007B3FC")
        self.assertEqual(summary["source_hash"], sha256("ラド".encode("shift_jis")))
        self.assertNotIn("code_units", summary)

    def test_byte_summary_is_hash_and_count_only(self) -> None:
        result = summarize_bytes(b"\x00\x01\x02", 0x02000000)
        self.assertEqual(result["address"], "0x02000000")
        self.assertEqual(result["length"], 3)
        self.assertEqual(result["nonzero_bytes"], 2)
        self.assertIn("sha256", result)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""ROM-independent tests for the bounded B3EJ M2 trace harness."""

from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("trace_m2_runtime.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_trace_m2_runtime", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load trace_m2_runtime.py")
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


class TraceM2RuntimeTest(unittest.TestCase):
    def test_sequence_expands_without_keeping_source_text(self) -> None:
        phases = TRACE.parse_sequence("none:2,start:3,none:1")
        self.assertEqual(TRACE.expand_sequence(phases), ["none", "none", "start", "start", "start", "none"])
        self.assertEqual(TRACE.key_value("none"), 0x03FF)
        self.assertEqual(TRACE.key_value("start"), 0x03F7)
        self.assertEqual(TRACE.pressed_mask("none"), 0)
        self.assertEqual(TRACE.pressed_mask("start"), 0x0008)

    def test_candidate_addresses_use_rom_pointer_space(self) -> None:
        candidate = TRACE.candidate_addresses()
        self.assertEqual(candidate["table_gba_address"], 0x080D1FFC)
        self.assertEqual(candidate["record_gba_address"], 0x08078528)
        self.assertEqual(candidate["record_payload_length"], 14)
        self.assertNotIn("text", candidate)

    def test_fixed_slot_variant_requires_an_explicit_contract(self) -> None:
        data = bytearray(0x0D2000)
        data[0xAC:0xB0] = b"B3EJ"
        data[0x0D1FFC:0x0D2000] = (0x08078528).to_bytes(4, "little")
        data[0x078528:0x07852C] = b"abc\0"
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(data)
            handle.flush()
            with self.assertRaises(ValueError):
                TRACE.static_candidate_metadata(pathlib.Path(handle.name))
            metadata = TRACE.static_candidate_metadata(
                pathlib.Path(handle.name), allow_fixed_slot_variant=True
            )
        self.assertEqual(metadata["record_variant"], "fixed-slot-variant")
        self.assertTrue(metadata["fixed_slot_within_reviewed_span"])
        self.assertEqual(metadata["reviewed_clean_record_payload_length"], 14)

    def test_vram_summary_reports_delta_not_bytes(self) -> None:
        before = bytes(64)
        after = bytearray(before)
        after[0] = 1
        after[33] = 2
        summary = TRACE.vram_summary(before, bytes(after))
        self.assertEqual(summary["changed_bytes"], 2)
        self.assertEqual(summary["changed_4bpp_tile_count"], 2)
        self.assertNotIn("data", summary)

    def test_m22_breakpoints_normalize_thumb_addresses(self) -> None:
        self.assertEqual(TRACE.M22_BREAKPOINTS["output_writer"], 0x0800CAD8)
        self.assertEqual(TRACE.M22_BREAKPOINTS["glyph_expand"], 0x080650DC)
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x0800CAD9), "output_writer")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x080650DD), "glyph_expand")
        self.assertEqual(TRACE.M22_SENTINEL_CODES[0x9594], "U+90E8")
        self.assertNotIn("text", TRACE.M22_BREAKPOINTS)

    def test_m22_index_metadata_keeps_local_and_table_bounds_separate(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int) -> bytes:
                fields = {
                    0x02000100: (2).to_bytes(2, "little"),
                    0x02000102: (6).to_bytes(2, "little"),
                    0x02000104: (1).to_bytes(2, "little"),
                    0x02000106: (1).to_bytes(2, "little"),
                    0x02000108: (1).to_bytes(2, "little"),
                    0x02000124: (0).to_bytes(2, "little"),
                    0x0200011C: (0x03000200).to_bytes(4, "little"),
                    0x03000205: bytes([0x85]),
                }
                return fields[address][:length]

        metadata = TRACE._r6_metadata(
            FakeClient(),
            {
                "r6": 0x02000100,
                "r7": 0x03000205,
                "r0": 0,
                "lr": 0x08026040,
            },
            entry_pc=False,
        )
        self.assertEqual(metadata["event_array_index"], 5)
        self.assertEqual(metadata["actual_index"], 5)
        self.assertTrue(metadata["event_array_index_less_than_local_length"])
        self.assertTrue(metadata["index_less_than_table_b_count"])
        self.assertEqual(metadata["bound_status"], "runtime-observed-only; not-static-proof")

    def test_m24_index_metadata_separates_local_count_and_table_bound(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int) -> bytes:
                fields = {
                    0x02000100: (2).to_bytes(2, "little"),
                    0x02000102: (6).to_bytes(2, "little"),
                    0x02000104: (1).to_bytes(2, "little"),
                    0x02000106: (1).to_bytes(2, "little"),
                    0x02000108: (1).to_bytes(2, "little"),
                    0x02000124: (0).to_bytes(2, "little"),
                    0x0200011C: (0x03000200).to_bytes(4, "little"),
                    0x03000205: bytes([0x85]),
                }
                return fields[address][:length]

        metadata = TRACE._r6_metadata(
            FakeClient(),
            {"r6": 0x02000100, "r7": 0x03000205, "r0": 0, "lr": 0x08026040},
            entry_pc=False,
        )
        self.assertTrue(metadata["actual_index_less_than_local_count"])
        self.assertTrue(metadata["index_less_than_table_b_count"])

    def test_m23_breakpoints_include_builder_and_pipeline_receipt_edges(self) -> None:
        self.assertEqual(TRACE.M23_MAX_COHORT_HITS, 32)
        self.assertEqual(TRACE.M23_BREAKPOINTS["event_builder_call"], 0x08026510)
        self.assertEqual(TRACE.M23_BREAKPOINTS["event_builder_exit"], 0x08019376)
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x08019377), "event_builder_exit")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x08065245), "glyph_expand_exit")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x080656E3), "vram_copy_call")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x080656E7), "vram_copy_exit")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x08008963), "tilemap_writer_exit")

    def test_m24_runtime_table_receipt_is_bounded_and_hash_only(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int) -> bytes:
                self.request = (address, length)
                return bytes([1, 43, 0xFF, 0x99])

        client = FakeClient()
        receipt = TRACE._bounded_runtime_table_receipt(client, scan_limit=4)
        self.assertEqual(client.request, (TRACE.M24_RUNTIME_TABLE_ADDRESS, 4))
        self.assertEqual(receipt["status"], "sentinel-found")
        self.assertEqual(receipt["count_before_sentinel"], 2)
        self.assertEqual(receipt["scanned_length"], 3)
        self.assertNotIn("data", receipt)
        self.assertNotIn("bytes", receipt)

    def test_m23_memory_receipt_hashes_without_retaining_bytes(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int) -> bytes:
                self.request = (address, length)
                return bytes(range(length))

        client = FakeClient()
        receipt = TRACE._memory_receipt(client, 0x02000000, 4)
        self.assertEqual(client.request, (0x02000000, 4))
        self.assertEqual(receipt["status"], "read")
        self.assertEqual(receipt["nonzero_byte_count"], 3)
        self.assertNotIn("data", receipt)
        self.assertNotIn("bytes", receipt)

    def test_m23_vram_copy_length_is_already_a_byte_count(self) -> None:
        class FakeClient:
            def read_memory(self, _address: int, length: int) -> bytes:
                return bytes(length)

        metadata = TRACE._pipeline_hit_metadata(
            FakeClient(),
            "vram_copy_call",
            {"pc": 0x080656E2, "lr": 0, "r0": 0x0600C000, "r1": 0x02000000, "r2": 0x80},
        )
        self.assertEqual(metadata["copy_length_bytes"], 0x80)
        self.assertNotIn("copy_length_units", metadata)

    def test_m23_pipeline_event_budget_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            TRACE.run_pipeline_trace(
                pathlib.Path("/not-used.gba"),
                host="127.0.0.1",
                port=24567,
                sequence=[],
                natural_events=33,
                controlled_events=1,
                event_timeout=0.1,
                settle_seconds=0.0,
                controlled_record=False,
            )

    def test_m23_controlled_consumer_fixture_is_explicit_and_bounded(self) -> None:
        metadata = TRACE.controlled_consumer_metadata()
        self.assertEqual(metadata["provenance"], "controlled-consumer-call-hijack")
        self.assertEqual(metadata["dispatch_index"], 20)
        self.assertEqual(metadata["event_byte_masked_index"], 0)
        self.assertTrue(metadata["index_less_than_table_b_count"])
        self.assertEqual(metadata["natural_reachability"], "not-claimed")
        self.assertNotIn("raw_bytes", metadata)


if __name__ == "__main__":
    unittest.main()

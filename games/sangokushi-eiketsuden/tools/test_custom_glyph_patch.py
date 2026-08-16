#!/usr/bin/env python3
"""ROM-independent tests for the bounded custom glyph encoder."""

from __future__ import annotations

import gzip
import importlib.util
import json
import pathlib
import tempfile
import unittest


def load(name: str):
    path = pathlib.Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PATCH = load("custom_glyph_patch")


class CustomGlyphPatchTest(unittest.TestCase):
    def test_mapping_normalizes_codepoint_unit_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "mapping.json"
            path.write_text(json.dumps({
                "revision": "B3EJ",
                "mappings": [{
                    "unicode": "U+7D93",
                    "code_unit": "0x8FD5",
                    "codepage_index": 1833,
                }],
            }), encoding="utf-8")
            result = PATCH.parse_mapping(path)
        entry = result["by_codepoint"][0x7D93]
        self.assertEqual(entry["code_unit"], 0x8FD5)
        self.assertEqual(entry["codepage_index"], 1833)
        self.assertEqual(entry["unicode"], "U+7D93")

    def test_mapping_rejects_duplicate_slots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "mapping.json"
            path.write_text(json.dumps({
                "revision": "B3EJ",
                "mappings": [
                    {"unicode": "U+7D93", "code_unit": "0x8FD5", "codepage_index": 1833},
                    {"unicode": "U+9A57", "code_unit": "0x8FD5", "codepage_index": 1832},
                ],
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                PATCH.parse_mapping(path)

    def test_custom_encoding_overrides_standard_encoder(self) -> None:
        mapping = {0x7D93: {"code_unit": 0x8FD5}}
        encoded, custom = PATCH.encode_text("經A", mapping)
        self.assertEqual(encoded, b"\x8f\xd5A")
        self.assertEqual(custom, [0x7D93])

    def test_target_codepage_gate_rejects_unlisted_standard_unit(self) -> None:
        with self.assertRaises(ValueError):
            PATCH._validate_target_codepage(b"\x99\xc8", [0x8173])
        PATCH._validate_target_codepage(b"\x81\x73A", [0x8173])

    def test_unifont_plane_reader_requires_16x16(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "font.hex.gz"
            with gzip.open(path, "wt", encoding="ascii") as stream:
                stream.write("7D93:" + "00" * 32 + "\n")
            planes = PATCH._read_font_planes(path, {0x7D93})
        self.assertEqual(len(planes[0x7D93][0]), 0x20)
        self.assertEqual(planes[0x7D93][1], bytes(0x20))

    def test_fixed_slot_replacement_keeps_original_span(self) -> None:
        self.assertEqual(PATCH.fixed_slot_replacement(b"ABCD", b"XY"), b"XY\0\0\0")
        with self.assertRaises(ValueError):
            PATCH.fixed_slot_replacement(b"AB", b"123")

    def test_pool_parser_is_strict(self) -> None:
        self.assertEqual(PATCH.parse_pool_entry("b3ej:system-item-class:003", "system-item-class"), 3)
        self.assertEqual(PATCH.parse_pool_entry("b3ej:table-b:020", "table-b"), 20)
        self.assertEqual(PATCH.parse_pool_entry("b3ej:event-system:023", "event-system"), 23)
        self.assertEqual(PATCH.parse_pool_entry("b3ej:story-event:032", "story-event"), 32)
        with self.assertRaises(ValueError):
            PATCH.parse_pool_entry("b3ej:table-c:001", "table-b")

    def test_story_pool_parser_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            PATCH.parse_pool_entry("b3ej:story-event:033", "story-event")


if __name__ == "__main__":
    unittest.main()

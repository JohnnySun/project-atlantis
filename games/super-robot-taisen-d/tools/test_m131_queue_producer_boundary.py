import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("m131_queue_producer_boundary", HERE / "m131_queue_producer_boundary.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


ROOT = HERE.parent
ROM = ROOT / "roms" / "base" / "Super_Robot_Taisen_D_JP_A6SJ.gba"
MANIFEST = ROOT / "research" / "m131-queue-caller-case.json"
LAYOUT = ROOT / "research" / "m128-control-layout-contract.json"


def negative_session() -> dict:
    return {
        "status": "unknown",
        "preflight": {"status": "free"},
        "ownership": {
            "process_matches_rom": True,
            "identity_changed": False,
            "ready": False,
            "listener_matches_exact_pid": False,
        },
        "runtime_exit": None,
        "cleanup": {"status": "killed_after_timeout"},
    }


class M131QueueProducerBoundaryTests(unittest.TestCase):
    def test_report_verifies_queue_context_and_keeps_semantics_opaque(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        identity = {
            "status": "pass",
            "rom": {"sha256": MODULE.EXPECTED_PATCHED_SHA256},
        }
        report = MODULE.build_report(ROM.read_bytes(), manifest, identity, negative_session(), layout)
        self.assertEqual(report["queue_context"]["queue_table"]["runtime_address"], "0x02011E20")
        self.assertEqual(report["queue_context"]["queue_table"]["entry_count"], 60)
        self.assertEqual(report["queue_context"]["argument_layout"]["r0"], "entry+0x08")
        self.assertTrue(report["queue_context"]["guard_and_call"]["entry_clear_after_consumer"])
        self.assertFalse(report["gate"]["natural_queue_callsite_observed"])
        self.assertFalse(report["gate"]["newline_semantics_proven"])
        self.assertFalse(report["gate"]["speaker_semantics_proven"])
        self.assertFalse(report["gate"]["branch_semantics_proven"])

    def test_report_has_no_forbidden_payload_keys(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        identity = {"status": "pass", "rom": {"sha256": MODULE.EXPECTED_PATCHED_SHA256}}
        report = MODULE.build_report(ROM.read_bytes(), manifest, identity, negative_session(), layout)
        encoded = json.dumps(report)
        for forbidden in ('"text"', '"source"', '"raw"', '"pixels"', '"screenshot"'):
            self.assertNotIn(forbidden, encoded)

    def test_changed_queue_instruction_rejects(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        identity = {"status": "pass", "rom": {"sha256": MODULE.EXPECTED_PATCHED_SHA256}}
        rom = bytearray(ROM.read_bytes())
        rom[0x08008E1C - MODULE.ROM_BASE] ^= 0x01
        with self.assertRaises(MODULE.QueueBoundaryReject):
            MODULE.build_report(bytes(rom), manifest, identity, negative_session(), layout)

    def test_session_must_prove_owned_cleanup(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        identity = {"status": "pass", "rom": {"sha256": MODULE.EXPECTED_PATCHED_SHA256}}
        session = negative_session()
        session["ownership"]["process_matches_rom"] = False
        with self.assertRaises(MODULE.QueueBoundaryReject):
            MODULE.build_report(ROM.read_bytes(), manifest, identity, session, layout)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / ".agents" / "skills" / "gba-runtime-validation" / "scripts" / "check_report.py"
SPEC = importlib.util.spec_from_file_location("gba_runtime_report_checker", CHECKER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report(status="pass"):
    return {
        "format": "project-atlantis-gba-runtime-validation-report-v1",
        "phase": "runtime",
        "status": status,
        "unknown_policy": "fail-closed",
        "diagnostics": [{"status": status, "code": "runtime.fixture", "message": "synthetic fixture"}],
        "evidence": {
            "case_id": "synthetic-report",
            "capabilities": {
                "required": ["gdb-remote"],
                "exercised": ["gdb-remote"],
                "unproven": [],
            },
        },
    }


class RuntimeReportCheckerTest(unittest.TestCase):
    def test_accepts_structurally_consistent_pass(self):
        self.assertEqual(MODULE.validate(report()), [])

    def test_rejects_pass_with_unproven_capability(self):
        candidate = report()
        candidate["evidence"]["capabilities"]["exercised"] = []
        candidate["evidence"]["capabilities"]["unproven"] = ["gdb-remote"]
        errors = MODULE.validate(candidate)
        self.assertIn("$.status: pass is forbidden with unproven capabilities", errors)

    def test_rejects_status_that_disagrees_with_diagnostics(self):
        candidate = report()
        candidate["diagnostics"][0]["status"] = "unknown"
        errors = MODULE.validate(candidate)
        self.assertIn("$.status: expected unknown from diagnostic reduction", errors)

    def test_rejects_raw_text_payload(self):
        candidate = report()
        candidate["evidence"]["text"] = "copyrighted payload"
        errors = MODULE.validate(candidate)
        self.assertIn("$.evidence.text: forbidden raw-content field", errors)


if __name__ == "__main__":
    unittest.main()

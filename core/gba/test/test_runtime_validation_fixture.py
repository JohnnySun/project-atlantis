#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gba.runtime_validation.static_checks import run_static  # noqa: E402


def load_fixture_builder():
    path = ROOT / "examples/gba-runtime-validation/build_fixture.py"
    spec = importlib.util.spec_from_file_location("gba_runtime_fixture", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build


class CopyrightFreeFixtureTest(unittest.TestCase):
    def test_all_declared_faults_reduce_to_expected_status(self):
        build = load_fixture_builder()
        expected = {
            "none": "pass",
            "adjacent": "fail",
            "pointer": "fail",
            "unterminated": "fail",
            "control": "fail",
            "control-arity": "fail",
            "encoding": "fail",
            "overflow": "fail",
            "unknown-width": "unknown",
            "alias": "fail",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for fault, status in expected.items():
                with self.subTest(fault=fault):
                    base, candidate, manifest = build(fault)
                    base_path = root / f"{fault}-base.gba"
                    candidate_path = root / f"{fault}-candidate.gba"
                    base_path.write_bytes(base)
                    candidate_path.write_bytes(candidate)
                    report = run_static(manifest, base_path, candidate_path)
                    self.assertEqual(report.status, status)
                    self.assertEqual(report.exit_code, {"pass": 0, "fail": 1, "unknown": 2}[status])


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("audit_control_consumption.py")
SPEC = importlib.util.spec_from_file_location("dqmch_audit_control_consumption", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ControlConsumptionTest(unittest.TestCase):
    def test_every_dispatch_control_has_a_shape(self) -> None:
        self.assertEqual(set(MODULE.CONSUMPTION), set(range(0xDF, 0x100)))
        self.assertEqual(MODULE.CONSUMPTION[0xF0], ("fixed-1", "source+18", "unconditional"))
        self.assertEqual(MODULE.CONSUMPTION[0xF4][0], "conditional-2")
        self.assertEqual(MODULE.CONSUMPTION[0xFA][0], "conditional-2")
        self.assertEqual(MODULE.CONSUMPTION[0xFF][0], "none")

    def test_signature_audit_is_independent_of_script_bytes(self) -> None:
        data = bytearray(0x800000)
        for address, expected, _label in MODULE.READ_SIGNATURES:
            offset = address - MODULE.ROM_BASE
            data[offset:offset + len(expected)] = expected
        rows = MODULE.audit_signatures(bytes(data))
        self.assertEqual(len(rows), len(MODULE.READ_SIGNATURES))

    def test_signature_audit_rejects_drift(self) -> None:
        data = bytearray(0x800000)
        address, expected, _label = MODULE.READ_SIGNATURES[0]
        offset = address - MODULE.ROM_BASE
        data[offset:offset + len(expected)] = bytes([expected[0] ^ 0x01]) + expected[1:]
        with self.assertRaises(ValueError):
            MODULE.audit_signatures(bytes(data))


if __name__ == "__main__":
    unittest.main()

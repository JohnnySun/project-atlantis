import unittest

try:
    from .audit_control_dispatch import (
        CONTROL_FIRST,
        HANDLERS,
        PARAMETER_SHAPES,
        TABLE_CPU,
        audit_table,
    )
except ImportError:
    from audit_control_dispatch import (
        CONTROL_FIRST,
        HANDLERS,
        PARAMETER_SHAPES,
        TABLE_CPU,
        audit_table,
    )


class ControlDispatchTest(unittest.TestCase):
    def test_expected_table_layout_is_complete(self) -> None:
        self.assertEqual(len(HANDLERS), 0x21)
        self.assertEqual(len(PARAMETER_SHAPES), len(HANDLERS))
        self.assertEqual(CONTROL_FIRST + len(HANDLERS) - 1, 0xFF)

    def test_clean_style_table_is_audited_without_script_reads(self) -> None:
        data = bytearray(0x800000)
        data[TABLE_CPU - 0x08000000 - 4:TABLE_CPU - 0x08000000] = (TABLE_CPU).to_bytes(4, "little")
        for index, handler in enumerate(HANDLERS):
            offset = TABLE_CPU - 0x08000000 + index * 4
            data[offset:offset + 4] = handler.to_bytes(4, "little")
        rows = audit_table(bytes(data))
        self.assertEqual(rows[0], (0xDF, HANDLERS[0], PARAMETER_SHAPES[0]))
        self.assertEqual(rows[8][2], "may-read-1")
        self.assertEqual(rows[9][2], "conditional-2")
        self.assertEqual(rows[0xF9 - CONTROL_FIRST][2], "read-1")
        self.assertEqual(rows[-1], (0xFF, HANDLERS[-1], PARAMETER_SHAPES[-1]))


if __name__ == "__main__":
    unittest.main()

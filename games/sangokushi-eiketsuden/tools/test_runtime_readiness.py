#!/usr/bin/env python3
"""ROM-independent tests for M2.3 process/port readiness metadata."""

from __future__ import annotations

import pathlib
import sys
import unittest


TOOL_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))
import runtime_readiness as readiness  # noqa: E402


class RuntimeReadinessTest(unittest.TestCase):
    def test_process_match_requires_exact_rom_path(self) -> None:
        rom = pathlib.Path("/private/tmp/B3EJ_JP_candidate.gba")
        command = "/private/tmp/mgba-headless -g /private/tmp/B3EJ_JP_candidate.gba"
        self.assertTrue(readiness.process_matches_rom(command, rom))
        self.assertFalse(readiness.process_matches_rom(command, pathlib.Path("/private/tmp/other.gba")))

    def test_listener_match_requires_pid_port_and_listen_state(self) -> None:
        output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "mgba 1234 user 5u IPv4 0x0 0t0 TCP 127.0.0.1:24567 (LISTEN)\n"
        )
        self.assertTrue(readiness.listener_matches_pid(output, 1234, 24567))
        self.assertFalse(readiness.listener_matches_pid(output, 1235, 24567))
        self.assertFalse(readiness.listener_matches_pid(output, 1234, 24568))

    def test_listener_match_rejects_header_only_or_non_listener(self) -> None:
        self.assertFalse(readiness.listener_matches_pid("COMMAND PID\n", 1234, 24567))
        output = "COMMAND PID USER FD TYPE NAME\nmgba 1234 user 5u TCP 127.0.0.1:24567\n"
        self.assertFalse(readiness.listener_matches_pid(output, 1234, 24567))


if __name__ == "__main__":
    unittest.main()

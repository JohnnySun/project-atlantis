from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from core.gba.runtime_session import (
    command_contains_rom,
    identity_matches,
    inspect_owner,
    launch_command,
    listener_pids,
)


class FakeRunner:
    def __init__(self, ps_output: str, lsof_output: str):
        self.ps_output = ps_output
        self.lsof_output = lsof_output

    def __call__(self, command, **kwargs):
        output = self.ps_output if command[0] == "ps" else self.lsof_output
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")


class RuntimeSessionTest(unittest.TestCase):
    def test_listener_parser_requires_requested_port_and_listen(self) -> None:
        output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "mgba 1234 user 5u IPv4 0x0 0t0 TCP 127.0.0.1:24567 (LISTEN)\n"
            "mgba 9999 user 6u IPv4 0x0 0t0 TCP 127.0.0.1:24568 (LISTEN)\n"
        )
        self.assertEqual(listener_pids(output, 24567), {1234})
        self.assertEqual(listener_pids(output.replace("(LISTEN)", ""), 24567), set())

    def test_command_requires_exact_resolved_rom_token(self) -> None:
        rom = Path("/private/tmp/My Game.gba")
        command = "/private/tmp/mgba -g '/private/tmp/My Game.gba'"
        self.assertTrue(command_contains_rom(command, rom))
        self.assertFalse(command_contains_rom(command, Path("/private/tmp/My.gba")))

    def test_inspection_requires_one_exact_listener_pid_and_rom(self) -> None:
        rom = Path("/private/tmp/game.gba")
        ps = "1234 1 Sun Aug 17 01:02:03 2026 /private/tmp/mgba -g /private/tmp/game.gba\n"
        lsof = "COMMAND PID USER FD TYPE NAME\nmgba 1234 u 5u TCP 127.0.0.1:24567 (LISTEN)\n"
        result = inspect_owner(1234, 24567, rom, runner=FakeRunner(ps, lsof))
        self.assertTrue(result["ready"])
        result = inspect_owner(1234, 24567, rom, runner=FakeRunner(ps, lsof + "mgba 9 u 6u TCP *:24567 (LISTEN)\n"))
        self.assertFalse(result["ready"])

    def test_identity_match_includes_start_and_command(self) -> None:
        expected = {"pid": 3, "ppid": 1, "start": "time", "command": "mgba -g game"}
        self.assertTrue(identity_matches(expected, dict(expected)))
        changed = {**expected, "start": "later"}
        self.assertFalse(identity_matches(expected, changed))

    def test_launch_command_uses_absolute_executable_and_rom(self) -> None:
        command = launch_command(Path("/private/tmp/mgba"), Path("/private/tmp/game.gba"), ["--foo"])
        self.assertEqual(command, ["/private/tmp/mgba", "--foo", "-g", "/private/tmp/game.gba"])


if __name__ == "__main__":
    unittest.main()

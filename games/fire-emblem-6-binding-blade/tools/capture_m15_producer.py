#!/usr/bin/env python3
"""Capture the FE6 M1.5 text-buffer producer without dumping source text.

Start the locally supplied AFEJ ROM in an isolated mGBA GDB session first,
then run this client from the repository root.  The output is deliberately a
safe recon receipt: addresses, an index, hashes, marker offsets, and the
renderer branch are retained; raw ROM/RAM bytes are never printed or written.

Example:
    python3 tools/capture_m15_producer.py --port 2346
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient  # noqa: E402


ENTRY = 0x080000C0
LOADER = 0x08013ACC
LOADER_CALL = 0x08013B04
LOADER_RETURN = 0x08013B08
COPY_WRAPPER = 0x0800384C
COPY_WRAPPER_BRANCH = 0x0800385E
RENDERER_CONTROL_BRANCH = 0x08098C78
POINTER_TABLE = 0x080F635C
EXPECTED_DEST = 0x02029404
BUFFER_LENGTH = 0x400
ROM_SOURCE = 0x080F2256
EXPECTED_INDEX = 3087


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def capture(port: int, timeout: float, branch_hits: int) -> None:
    with GdbClient(port=port, timeout=timeout, packet_delay=0.05) as gdb:
        print(f"initial_stop={gdb.request('?')}")

        gdb.set_breakpoint(ENTRY)
        print(f"entry_stop={gdb.continue_until_stop(timeout)}")
        gdb.remove_breakpoint(ENTRY)

        gdb.set_breakpoint(LOADER_CALL)
        print(f"loader_call_stop={gdb.continue_until_stop(timeout)}")
        call_regs = gdb.read_registers()
        frame_index = int.from_bytes(gdb.read_memory(call_regs["r7"], 4), "little")
        source = call_regs["r0"]
        destination = call_regs["r1"]
        caller_lr = call_regs["lr"]
        table_entry = POINTER_TABLE + frame_index * 4
        print(f"loader={hex32(LOADER)}")
        print(f"pointer_table={hex32(POINTER_TABLE)}")
        print(f"table_index={frame_index}")
        print(f"table_entry={hex32(table_entry)}")
        print(f"source_pointer={hex32(source)}")
        print(f"destination={hex32(destination)}")
        print(f"runtime_caller_lr={hex32(caller_lr)}")
        if source != ROM_SOURCE or destination != EXPECTED_DEST:
            raise RuntimeError(
                "unexpected loader arguments; refuse to report a different path"
            )
        if frame_index != EXPECTED_INDEX:
            raise RuntimeError(
                f"unexpected loader index {frame_index}; expected {EXPECTED_INDEX}"
            )
        gdb.remove_breakpoint(LOADER_CALL)

        gdb.set_breakpoint(COPY_WRAPPER_BRANCH)
        print(f"copy_wrapper_stop={gdb.continue_until_stop(timeout)}")
        copy_regs = gdb.read_registers()
        copy_worker = copy_regs["r2"]
        print(f"copy_wrapper_source={hex32(copy_regs['r0'])}")
        print(f"copy_wrapper_destination={hex32(copy_regs['r1'])}")
        print(f"copy_worker={hex32(copy_worker)}")
        if copy_regs["r0"] != source or copy_regs["r1"] != destination:
            raise RuntimeError("copy wrapper arguments differ from loader arguments")
        if copy_worker != 0x0300323C:
            raise RuntimeError(f"unexpected copy worker {hex32(copy_worker)}")
        gdb.remove_breakpoint(COPY_WRAPPER_BRANCH)

        gdb.set_watchpoint(EXPECTED_DEST, kind=4, watch_type=2)
        write_stop = gdb.continue_until_stop(timeout)
        write_regs = gdb.read_registers()
        print(f"ewram_write_watch_stop={write_stop}")
        print(f"ewram_write_watch_r1={hex32(write_regs['r1'])}")
        print(f"ewram_write_watch_lr={hex32(write_regs['lr'])}")
        if "watch:02029404;" not in write_stop:
            raise RuntimeError("expected EWRAM write-watchpoint did not fire")
        gdb.remove_watchpoint(EXPECTED_DEST, kind=4, watch_type=2)

        gdb.set_breakpoint(LOADER_RETURN)
        print(f"loader_return_stop={gdb.continue_until_stop(timeout)}")
        buffer = gdb.read_memory(EXPECTED_DEST, BUFFER_LENGTH)
        nonzero = [offset for offset, value in enumerate(buffer) if value]
        last_nonzero = nonzero[-1] if nonzero else None
        terminator = next(
            (offset for offset in range((last_nonzero or -1) + 1, len(buffer))
             if buffer[offset] == 0),
            None,
        )
        controls = [offset for offset, value in enumerate(buffer) if value == 0x01]
        print(f"copy_wrapper={hex32(COPY_WRAPPER)}")
        print(f"buffer_sha256={hashlib.sha256(buffer).hexdigest()}")
        print(f"buffer_nonzero_count={len(nonzero)}")
        print(f"buffer_last_nonzero={last_nonzero}")
        print(f"buffer_first_zero_after_text={terminator}")
        print(f"buffer_control_0x01_offsets={controls}")
        if destination != EXPECTED_DEST:
            raise RuntimeError("destination is not the confirmed EWRAM buffer")
        gdb.remove_breakpoint(LOADER_RETURN)

        gdb.set_breakpoint(RENDERER_CONTROL_BRANCH)
        for index in range(branch_hits):
            stop = gdb.continue_until_stop(timeout)
            regs = gdb.read_registers()
            pointer = regs["r6"]
            value = gdb.read_memory(pointer, 1)[0]
            offset = pointer - EXPECTED_DEST
            print(
                "renderer_branch="
                f"{index} stop={stop} pc={hex32(regs['pc'])} "
                f"buffer_offset={offset} byte=0x{value:02x}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2346)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--branch-hits", type=int, default=2)
    args = parser.parse_args()
    capture(args.port, args.timeout, args.branch_hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

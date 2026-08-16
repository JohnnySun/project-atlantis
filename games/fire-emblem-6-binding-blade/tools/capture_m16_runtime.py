#!/usr/bin/env python3
"""Capture the bounded AFEJ M1.6 runtime receipt for index 3087.

Start an isolated mGBA GDB session with the reviewed AFEJ ROM, then run this
client.  It records only addresses, the table index, hashes, lengths and
marker offsets.  It never writes the ROM and never emits a RAM or source dump.
The default run observes natural index 3087; ``--index`` may safely replace
the loader's first argument at the loader-entry breakpoint for an adjacent
same-table probe.

Example::

    PYTHONDONTWRITEBYTECODE=1 python3 tools/capture_m16_runtime.py \
        --port 23901 --output work/afej-m16-runtime-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient  # noqa: E402


ENTRY = 0x080000C0
LOADER_REGION_START = 0x08013ACC
LOADER_ENTRY = 0x08013AD0
LOADER_CALL = 0x08013B04
LOADER_RETURN = 0x08013B08
COPY_WRAPPER_BRANCH = 0x0800385E
POINTER_TABLE = 0x080F635C
EXPECTED_DEST = 0x02029404
BUFFER_LENGTH = 0x400
EXPECTED_INDEX = 3087
EXPECTED_WORKER = 0x0300323C
EXPECTED_RUNTIME_SHA256 = (
    "792667cef3da14699e533dd04573bb90c7f53a79546519d60a0c328023d5359f"
)


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def marker_offsets(buffer: bytes) -> dict[str, list[int]]:
    return {
        f"0x{marker:02x}": [
            offset for offset, value in enumerate(buffer) if value == marker
        ]
        for marker in (0x00, 0x01, 0x04, 0xFF)
    }


def capture(port: int, timeout: float, requested_index: int) -> dict[str, object]:
    if not 0 <= requested_index < 3342:
        raise RuntimeError("requested index is outside the proven table domain")

    with GdbClient(port=port, timeout=timeout, packet_delay=0.05) as gdb:
        initial_stop = gdb.request("?")

        gdb.set_breakpoint(ENTRY)
        entry_stop = gdb.continue_until_stop(timeout)
        gdb.remove_breakpoint(ENTRY)

        # This stop is before the loader's stack spill, so it proves that the
        # runtime index arrives as its first argument rather than being
        # inferred only from a table range.
        gdb.set_breakpoint(LOADER_ENTRY)
        loader_entry_stop = gdb.continue_until_stop(timeout)
        loader_entry_regs = gdb.read_registers()
        natural_index = loader_entry_regs["r0"]
        gdb.write_register(0, requested_index)
        gdb.remove_breakpoint(LOADER_ENTRY)

        gdb.set_breakpoint(LOADER_CALL)
        loader_call_stop = gdb.continue_until_stop(timeout)
        call_regs = gdb.read_registers()
        frame_index = int.from_bytes(gdb.read_memory(call_regs["r7"], 4), "little")
        source = call_regs["r0"]
        destination = call_regs["r1"]
        caller_lr = call_regs["lr"]
        table_entry = POINTER_TABLE + frame_index * 4
        expected_source = int.from_bytes(gdb.read_memory(table_entry, 4), "little")
        if frame_index != requested_index:
            raise RuntimeError(
                f"unexpected stack index {frame_index}; expected {requested_index}"
            )
        if source != expected_source or destination != EXPECTED_DEST:
            raise RuntimeError(
                "loader arguments differ from the reviewed AFEJ producer path"
            )
        gdb.remove_breakpoint(LOADER_CALL)

        gdb.set_breakpoint(COPY_WRAPPER_BRANCH)
        wrapper_stop = gdb.continue_until_stop(timeout)
        wrapper_regs = gdb.read_registers()
        if (
            wrapper_regs["r0"] != source
            or wrapper_regs["r1"] != destination
            or wrapper_regs["r2"] != EXPECTED_WORKER
        ):
            raise RuntimeError("copy wrapper arguments differ from loader path")
        gdb.remove_breakpoint(COPY_WRAPPER_BRANCH)

        gdb.set_watchpoint(EXPECTED_DEST, kind=4, watch_type=2)
        write_stop = gdb.continue_until_stop(timeout)
        write_regs = gdb.read_registers()
        if "watch:02029404;" not in write_stop:
            raise RuntimeError("EWRAM buffer write watchpoint did not fire")
        gdb.remove_watchpoint(EXPECTED_DEST, kind=4, watch_type=2)

        gdb.set_breakpoint(LOADER_RETURN)
        loader_return_stop = gdb.continue_until_stop(timeout)
        buffer = gdb.read_memory(EXPECTED_DEST, BUFFER_LENGTH)
        gdb.remove_breakpoint(LOADER_RETURN)

    nonzero = [offset for offset, value in enumerate(buffer) if value]
    last_nonzero = nonzero[-1] if nonzero else None
    first_zero_after_text = next(
        (
            offset
            for offset in range((last_nonzero or -1) + 1, len(buffer))
            if buffer[offset] == 0
        ),
        None,
    )
    digest = hashlib.sha256(buffer).hexdigest()
    if requested_index == EXPECTED_INDEX and digest != EXPECTED_RUNTIME_SHA256:
        raise RuntimeError(f"runtime buffer hash drifted: {digest}")

    logical_end = (
        first_zero_after_text + 1
        if first_zero_after_text is not None
        else len(buffer)
    )

    return {
        "schema": "afej-m16-runtime-receipt-v1",
        "game": "fire-emblem-6-binding-blade",
        "revision": "AFEJ",
        "initial_stop": initial_stop,
        "entry_stop": entry_stop,
        "loader_region_start": hex32(LOADER_REGION_START),
        "loader_entry": hex32(LOADER_ENTRY),
        "loader_entry_stop": loader_entry_stop,
        "loader_entry_natural_index": natural_index,
        "loader_entry_requested_index": requested_index,
        "loader_call": hex32(LOADER_CALL),
        "loader_call_stop": loader_call_stop,
        "table_index": frame_index,
        "table_entry": hex32(table_entry),
        "source_pointer": hex32(source),
        "table_source_pointer": hex32(expected_source),
        "destination": hex32(destination),
        "runtime_caller_lr": hex32(caller_lr),
        "copy_worker": hex32(wrapper_regs["r2"]),
        "copy_wrapper_stop": wrapper_stop,
        "ewram_write_watch_stop": write_stop,
        "ewram_write_watch_r1": hex32(write_regs["r1"]),
        "loader_return_stop": loader_return_stop,
        "buffer_length": len(buffer),
        "buffer_sha256": digest,
        "buffer_nonzero_count": len(nonzero),
        "buffer_last_nonzero": last_nonzero,
        "buffer_first_zero_after_text": first_zero_after_text,
        # Do not report the zero-filled tail of the fixed EWRAM buffer as a
        # thousand separate terminators; the logical payload ends at the
        # first observed zero after its last nonzero byte.
        "control_marker_offsets": marker_offsets(buffer[:logical_end]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2346)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--index", type=int, default=EXPECTED_INDEX)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        receipt = capture(args.port, args.timeout, args.index)
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

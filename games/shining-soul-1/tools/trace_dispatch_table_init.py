#!/usr/bin/env python3
"""Session 16 recon: find the boot-time code that populates the IWRAM
"category -> glyph-pool-struct pointer" dispatch table at 0x030065f0
(session 11, research/obj-sentence-category4-and-dispatch-table.md).

Approach history (see README "第十六輪偵察" for the full story): a direct
WRITE watchpoint on 0x030065f0 itself never fires, even across a clean,
generous single continuous run from true reset (pc=0) all the way past
the point where the table is confirmed (by reading it back) to already
hold its final values - while a control test (WRITE watch on DISPCNT,
0x04000000) fires instantly and correctly. This rules out "watchpoints
don't work in this environment" and points at the write mechanism itself
bypassing mgba's CPU-instruction-level watch checks - most likely a BIOS
CpuSet/CpuFastSet bulk copy (the same mechanism sessions 3/7 found moving
font tiles into VRAM, confirmed via the wrapper stubs at ROM file offset
0x503bc/0x503c0: "svc #0xc; bx lr" and "svc #0xb; bx lr").

Static evidence supporting this: the dispatch table's 5 known non-null
entries (categories 0-4) are NOT independently stored literals anywhere
in the ROM (byte-exact search for the full pointer set found nothing) -
but they turn out to be an exact arithmetic progression, entry(i) =
0x08469344 + i*0x9A20 for i in 0..4 (verified: all four consecutive
deltas are exactly 0x9A20). And every literal-pool occurrence of the raw
value 0x030065f0 in the ROM (4 total, found via static search) resolves
to a READER (the already-known string-walk function at file offset
0xe8bc and near-duplicate sibling functions), never a writer. So the
value never needs to appear as a ROM literal in a writer either, which
is consistent with initialization via a BIOS block-copy whose destination
pointer is computed via register arithmetic rather than loaded from a
fixed literal pool slot.

This script catches every call to the two known BIOS-copy wrapper stubs
during a full boot run (breakpoint, not watchpoint - breakpoints proved
reliable for the DISPCNT control test's underlying mechanism and are a
different code path in mgba than data watchpoints), and reports any call
whose destination argument lands in or near the dispatch table's IWRAM
region (0x03006000-0x03007000, generously bracketing 0x030065f0).

BIOS CpuSet/CpuFastSet calling convention (confirmed session 3): r0 =
source pointer, r1 = dest pointer, r2 = length/mode word (bit 24 selects
16-bit vs 32-bit fixed-size transfer, bits 0-20 are the word/halfword
count).

Usage:
    python3 trace_dispatch_table_init.py [--max-hits 200] [--only-iwram]
    # requires: a FRESH mgba -g <rom>, not yet continued past reset.

Writes nothing to the ROM file; only reads/pokes live emulator state.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbstub_client import GdbClient  # noqa: E402

CPUFASTSET_WRAPPER = 0x080503bc
CPUSET_WRAPPER = 0x080503c0
IWRAM_LO = 0x03000000
IWRAM_HI = 0x03008000
DISPATCH_LO = 0x03006000
DISPATCH_HI = 0x03007000


def classify(addr):
    if IWRAM_LO <= addr < IWRAM_HI:
        tag = "IWRAM"
        if DISPATCH_LO <= addr < DISPATCH_HI:
            tag += " **NEAR DISPATCH TABLE**"
        return tag
    if 0x08000000 <= addr < 0x0A000000:
        return "ROM"
    if 0x02000000 <= addr < 0x02040000:
        return "EWRAM"
    if 0x06000000 <= addr < 0x06018000:
        return "VRAM"
    if 0x05000000 <= addr < 0x05000400:
        return "PALETTE"
    if 0x07000000 <= addr < 0x07000400:
        return "OAM"
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--max-hits", type=int, default=250)
    ap.add_argument("--per-iter-timeout", type=float, default=4.0)
    ap.add_argument("--max-iterations", type=int, default=400)
    ap.add_argument("--only-iwram", action="store_true",
                     help="only print hits whose r1 (dest) lands in IWRAM")
    args = ap.parse_args()

    c = GdbClient(args.host, args.port, timeout=10.0)
    print(f"connecting to {args.host}:{args.port} (expecting target halted at reset)...")
    c.connect()
    c.send("qSupported:multiprocess+")
    print("stop:", c.send("?"))
    regs0 = c.read_registers()
    print(f"  initial pc=0x{regs0[15]:08x}")
    gamecode = c.read_mem(0x080000AC, 4)
    if gamecode != b"AHUJ":
        print(f"  ABORT: wrong ROM connected (game_code={gamecode!r})")
        c.close()
        sys.exit(3)
    if regs0[15] != 0:
        print("  [warn] pc != 0, not a true fresh-reset connection")

    print(f"arming breakpoints at CpuFastSet wrapper 0x{CPUFASTSET_WRAPPER:08x} "
          f"and CpuSet wrapper 0x{CPUSET_WRAPPER:08x}...")
    c.set_breakpoint(CPUFASTSET_WRAPPER, kind=2, wtype=1)
    c.set_breakpoint(CPUSET_WRAPPER, kind=2, wtype=1)

    hits = []
    iterations = 0
    dispatch_hits = []
    try:
        while len(hits) < args.max_hits and iterations < args.max_iterations:
            iterations += 1
            try:
                stop = c.cont_and_wait(timeout=args.per_iter_timeout)
            except TimeoutError:
                try:
                    c.interrupt()
                except TimeoutError:
                    pass
                continue
            regs = c.read_registers()
            pc, lr = regs[15], regs[14]
            if pc not in (CPUFASTSET_WRAPPER, CPUSET_WRAPPER):
                # some other stop (shouldn't normally happen with only these
                # two breakpoints armed, but be defensive)
                continue
            which = "CpuFastSet" if pc == CPUFASTSET_WRAPPER else "CpuSet"
            r0, r1, r2 = regs[0], regs[1], regs[2]
            near_dispatch = DISPATCH_LO <= r1 < DISPATCH_HI
            hit = {"n": len(hits) + 1, "which": which, "lr": lr,
                   "r0": r0, "r1": r1, "r2": r2, "near_dispatch": near_dispatch}
            hits.append(hit)
            if near_dispatch:
                dispatch_hits.append(hit)
            if near_dispatch or not args.only_iwram:
                marker = "  <<<< DEST NEAR DISPATCH TABLE" if near_dispatch else ""
                print(f"  [{which} #{hit['n']}] lr=0x{lr:08x} src(r0)=0x{r0:08x} ({classify(r0)}) "
                      f"dest(r1)=0x{r1:08x} ({classify(r1)}) mode(r2)=0x{r2:08x}{marker}")
            c.send("s")  # step past the breakpoint so we don't re-hit forever
        if iterations >= args.max_iterations:
            print(f"  [reached max_iterations={args.max_iterations}, stopping]")
    finally:
        try:
            c.remove_breakpoint(CPUFASTSET_WRAPPER, kind=2, wtype=1)
            c.remove_breakpoint(CPUSET_WRAPPER, kind=2, wtype=1)
        except Exception as e:
            print(f"  [warn] cleanup failed: {e}")

    print(f"\ntotal BIOS-copy calls captured: {len(hits)}")
    print(f"calls with dest landing near dispatch table region: {len(dispatch_hits)}")
    for h in dispatch_hits:
        print(f"  {h}")

    raw = c.read_mem(0x030065f0, 16 * 4)
    entries = struct.unpack("<16I", raw)
    print("\nfinal dispatch table content:")
    for i, e in enumerate(entries):
        print(f"  category {i:2d}: 0x{e:08x}")

    c.close()
    print("\ndone, connection closed.")


if __name__ == "__main__":
    main()

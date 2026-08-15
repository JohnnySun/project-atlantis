#!/usr/bin/env python3
"""Read-only(ish) recon (session 8): find the RAM array that actually
holds the per-sprite "which glyph" data for a rendered sentence, by
single-stepping/breakpointing the enqueue call site itself.

Session 7 found: ROM file offset 0x080034d0 is `bl 0x8001154`, called
once per visible sprite from a loop (0x080033a4-0x080034e8) that walks a
fixed-count list. Session 7 traced r0 (the *resolved* ROM source address
of the glyph pixel data) at the moment of the call and confirmed it steps
through the known ROM addresses of "職業を選んでください"'s glyphs in
order - but could not find where the *character identity* itself (as
opposed to the already-resolved pixel address) is stored.

This session statically disassembled the loop body in detail (see
research/obj-sentence-glyph-loader.md session-8 section) and found the
resolved source address is computed at 0x080034b2-0x080034ca as:

    tile_index = (halfword@[r8+4] & 0x3FF) | ((byte@[r8+5] bits[6:7]) << 10)
    r0 (src)   = [sp+0x48] + tile_index * 32

where r8 (captured into `ip` at the top of each loop iteration, file
offset 0x33a4 `mov ip, r8`) is itself walked with an 8-byte stride per
iteration (file offset 0x34dc-0x34de: `add r8, #8`) - i.e. r8 is a
genuine per-sprite array with small, constant stride, exactly the "source
pointer that advances by a small stride each iteration" pattern the task
asked to look for. Each 8-byte entry has the same field layout as a
standard GBA OAM attribute set (attr0/attr1/attr2 + padding), and bytes
[r8+4..5] hold what's being decoded above as an (extended) OBJ tile
number.

This script breaks at the call site (0x080034d0) itself while parked on
the job-select screen (where the loop refires every frame, so we don't
need to catch a precise mid-transition instant - just wait on the
steady-state screen and let many passes go by), and for each hit dumps:
  - r0 (resolved ROM source address - lets us identify *which* glyph this
    iteration is, by comparison against session 5/6/7's known addresses)
  - r12/ip (the r8 array pointer for *this* iteration)
  - the raw 8 bytes at [r12] (the OAM-format descriptor entry itself)
  - [sp+0x48] (the glyph-table base pointer used in the address calc)
and cross-checks the reverse-engineered tile_index formula against the
known r0 value.

Usage:
    python3 trace_glyph_source_array.py --out-dir /tmp/ss1_trace8
    # requires: mgba -g <rom> already running in the background, and
    # requires having already navigated to the job-select screen (this
    # script does that navigation itself, reusing the session 3/5/6
    # button-injection technique).

Writes nothing to the ROM file; only pokes emulator registers/memory to
inject button presses and set breakpoints, exactly like
navigate_to_char_create.py.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

KEYINPUT = 0x04000130
DISPCNT = 0x04000000
VRAM = 0x06000000

NOTHING_PRESSED = 0x3FF
BTN_A = 0x01
BTN_START = 0x08

CALL_SITE = 0x080034d0  # bl 0x8001154, inside the sprite-visit loop

# Session 5/6/7-confirmed ROM source addresses for each of the 10 glyphs
# of "職業を選んでください" (research/obj-sentence-glyph-loader.md).
KNOWN_GLYPHS = {
    0x08482424: "職",
    0x0848eec4: "業",
    0x0846c1e4: "を",
    0x08487fc4: "選",
    0x0846c264: "ん",
    0x0846c964: "で",
    0x0846af64: "く",
    0x0846c7e4: "だ",
    0x0846b0e4: "さ",
    0x0846ac64: "い",
}

MAIN_TABLE_BASE = 0x08000000 + 0x46abe4


def read_dispcnt(c):
    return int.from_bytes(c.read_mem(DISPCNT, 2), "little")


def wait_for_dispcnt(c, target, timeout_s=20.0, poll_chunk=1.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        c.cont()
        time.sleep(poll_chunk)
        c.interrupt()
        val = read_dispcnt(c)
        print(f"  DISPCNT=0x{val:04x} (want 0x{target:04x})")
        if val == target:
            return True
    return False


def settle(c, seconds):
    c.cont()
    time.sleep(seconds)
    c.interrupt()


def press_button(c, mask_to_hold, hold_frames=28, release_frames=6,
                  per_hit_timeout=10.0, dest_reg=1, poll_pc=None):
    c.set_watchpoint(KEYINPUT, kind=2, wtype=3)
    try:
        total = hold_frames + release_frames
        for i in range(total):
            stop = c.cont_and_wait(timeout=per_hit_timeout)
            kind, addr = parse_stop_watch(stop)
            regs = c.read_registers()
            pc = regs[15]
            if poll_pc is not None and pc != poll_pc and i == 0:
                print(f"  [note] first hit pc=0x{pc:08x} (expected 0x{poll_pc:08x})")
            value = mask_to_hold if i < hold_frames else NOTHING_PRESSED
            c.write_register(dest_reg, value)
    finally:
        c.remove_watchpoint(KEYINPUT, kind=2, wtype=3)


def decode_tile_index(entry8: bytes):
    # halfword at +4 (little-endian), byte at +5's bits [6:7]
    hw4 = entry8[4] | (entry8[5] << 8)
    low10 = hw4 & 0x3FF
    high2 = (entry8[5] >> 6) & 0x3
    return low10 | (high2 << 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--out-dir", default="/tmp/ss1_trace8")
    ap.add_argument("--max-hits", type=int, default=40)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    c = GdbClient(args.host, args.port, timeout=8.0)
    print(f"connecting to {args.host}:{args.port} ...")
    c.connect()
    print("qSupported:", c.send("qSupported:multiprocess+"))
    print("?:", c.send("?"))

    print("Step 1: free-run to stable title screen (DISPCNT==0x1240)...")
    if not wait_for_dispcnt(c, 0x1240, timeout_s=20.0):
        print("TIMEOUT: never saw title-screen DISPCNT. Aborting.")
        sys.exit(2)
    settle(c, 4.0)

    print("Step 2: press Start+A to leave title -> mode-select...")
    press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A), poll_pc=0x0800077a)
    settle(c, 1.5)

    print("Step 3: press A to confirm single-player mode -> save-select...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 1.5)
    print(f"  save-select DISPCNT=0x{read_dispcnt(c):04x} (want 0x1d40)")

    print("Step 4: press A to select FILE 1 -> job-select screen...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 2.5)
    print(f"  job-select DISPCNT=0x{read_dispcnt(c):04x}")

    print(f"Step 5: arming hardware breakpoint at 0x{CALL_SITE:08x} "
          "(the bl into the enqueue function, inside the per-sprite "
          "visit loop) and letting it refire across several frames "
          "(no need to catch the transition instant - this loop reruns "
          "every frame on the steady-state screen)...")
    c.set_breakpoint(CALL_SITE, kind=2, wtype=1)

    hits = []
    try:
        for i in range(args.max_hits):
            stop = c.cont_and_wait(timeout=10.0)
            regs = c.read_registers()
            pc = regs[15]
            if pc != CALL_SITE:
                print(f"  [warn] hit #{i}: pc=0x{pc:08x} != call site, stop={stop!r}")
                # still record; single-step past whatever this was
                c.send("s")
                continue
            r0 = regs[0]
            r12 = regs[12]
            sp = regs[13]
            entry = c.read_mem(r12, 8)
            base_ptr = int.from_bytes(c.read_mem(sp + 0x48, 4), "little")
            tile_idx = decode_tile_index(entry)
            predicted_r0 = base_ptr + tile_idx * 32
            glyph = KNOWN_GLYPHS.get(r0, "?")
            match = "OK" if predicted_r0 == r0 else "MISMATCH"
            char_idx = tile_idx // 4
            main_table_predicted = MAIN_TABLE_BASE + char_idx * 0x80
            line = (f"hit#{i:02d} r0=0x{r0:08x}({glyph}) r12(src-array-ptr)=0x{r12:08x} "
                    f"entry={entry.hex()} tile_idx={tile_idx} char_idx={char_idx} "
                    f"base_ptr=0x{base_ptr:08x} predicted_r0=0x{predicted_r0:08x}[{match}] "
                    f"main_table_formula=0x{main_table_predicted:08x}")
            print(" ", line)
            hits.append(line)
            # single-step past the breakpoint before continuing, or we'd
            # just re-trap on the same bl forever (per session 3's
            # watchpoint lesson - same caution applies to breakpoints on
            # this stub).
            c.send("s")
    finally:
        c.remove_breakpoint(CALL_SITE, kind=2, wtype=1)

    with open(os.path.join(args.out_dir, "hits.txt"), "w") as f:
        f.write("\n".join(hits) + "\n")
    print(f"\nWrote {len(hits)} hits to {args.out_dir}/hits.txt")

    c.close()
    print("done, connection closed.")


if __name__ == "__main__":
    main()

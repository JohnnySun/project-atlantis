#!/usr/bin/env python3
"""Read-only(ish) recon (session 11): read the live IWRAM "category ->
glyph-pool-struct pointer" dispatch table the OBJ-sentence string-walk
function (ROM file offset 0x0800e8bc, decoded session 8) actually uses at
runtime, instead of guessing glyph-table bases by static pattern
extrapolation.

Background: disassembling the string-walk loop (file offset 0xe8f0-e8fe,
capstone THUMB, /usr/bin/python3) shows

    r0 = (code & 0xf00) >> 6        ; = category * 4
    r1 = *(pc_literal)              ; ldr r1,[pc,#0x54] at file offset
                                     ; 0xe8f8 -> literal at file offset
                                     ; 0xe950 -> value 0x030065f0
    r0 = r0 + r1                    ; pool_ptr_table + category*4
    r1 = *(r0)                      ; the actual per-category entry

0x030065f0 is an IWRAM address (GBA IWRAM = 0x03000000-0x03007FFF), not a
ROM literal - the table is populated at runtime (boot init), so it cannot
be read by pure static ROM analysis; this script connects to a live mGBA
and reads it directly.

Session 11 finding: only categories 0-4 have non-zero entries; categories
5-15 are hard 0x00000000 in this table, both at the title screen (first
sample, ~3s after boot) and again at the deepest screen reached so far
(name-entry, after title->mode-select->save-select->job-select->
color-select->name-entry). Since this is evidently a boot-time constant
(identical at both sample points, several screens apart), this is strong
evidence categories 5-15 are simply not wired to any glyph pool in this
dispatch mechanism at all - not "unsolved", but "not used" for OBJ-sentence
rendering. See research/obj-sentence-category4-and-dispatch-table.md.

Each non-zero entry is a pointer to a small per-category struct, NOT the
glyph pixel-table base directly. Session 11 found (by cross-referencing
categories 1/2/3's already-known, independently-verified pixel-table
bases - see obj-sentence-kanji-categories.md) that

    pixel_table_base(category)  = entry(category) + 0x1820   (category != 0)
    pixel_table_base(0)         = entry(0)         + 0x18a0

holds exactly for all three of categories 1/2/3 (zero free parameters,
3-point fit), and applying it to category 4's entry predicts
0x4913e4 - independently confirmed via hijack_and_capture_glyph_sources.py
against two real corpus glyphs. This script prints both the raw entry and
this computed candidate base for every non-zero entry, so a future session
extending this table (should any of 5-15 ever become non-zero, e.g. if a
sequel/version has more categories wired up) gets the derived base for
free.

Usage:
    python3 dump_category_dispatch_table.py [--screen title|name-entry]
    # requires: mgba -g <rom> already running in the background (fresh
    # instance - kill any stray prior one first, mGBA's GDB stub does not
    # accept a second connection cleanly).

Writes nothing to the ROM file; only reads emulator memory (and, for
--screen name-entry, pokes registers to inject the same button sequence
navigate_to_char_create.py uses to get there).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbstub_client import GdbClient  # noqa: E402

KEYINPUT = 0x04000130
DISPCNT = 0x04000000
NOTHING_PRESSED = 0x3FF
BTN_A = 0x01
BTN_START = 0x08

DISPATCH_TABLE_ADDR = 0x030065f0
NUM_CATEGORIES = 16
STRUCT_TO_PIXEL_OFFSET = 0x1820          # categories 1-15
STRUCT_TO_PIXEL_OFFSET_CAT0 = 0x18a0     # category 0's extra glyph_entry_index -1 offset


def read_dispcnt(c):
    return int.from_bytes(c.read_mem(DISPCNT, 2), "little")


def wait_for_dispcnt(c, target, timeout_s=20.0, poll_chunk=1.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        c.cont()
        time.sleep(poll_chunk)
        c.interrupt()
        if read_dispcnt(c) == target:
            return True
    return False


def settle(c, seconds):
    c.cont()
    time.sleep(seconds)
    c.interrupt()


def press_button(c, mask_to_hold, hold_frames=28, release_frames=6, per_hit_timeout=10.0, dest_reg=1):
    c.set_watchpoint(KEYINPUT, kind=2, wtype=3)
    try:
        total = hold_frames + release_frames
        for i in range(total):
            c.cont_and_wait(timeout=per_hit_timeout)
            value = mask_to_hold if i < hold_frames else NOTHING_PRESSED
            c.write_register(dest_reg, value)
    finally:
        c.remove_watchpoint(KEYINPUT, kind=2, wtype=3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--screen", choices=["title", "name-entry"], default="title",
                     help="how far to navigate before sampling (default: title, "
                          "since session 11 found the table is a boot-time constant)")
    args = ap.parse_args()

    c = GdbClient(args.host, args.port, timeout=8.0)
    print(f"connecting to {args.host}:{args.port} ...")
    c.connect()
    c.send("qSupported:multiprocess+")
    c.send("?")

    if not wait_for_dispcnt(c, 0x1240, timeout_s=20.0):
        print("TIMEOUT waiting for title screen.")
        sys.exit(2)
    settle(c, 4.0)

    if args.screen == "name-entry":
        print("Navigating: title -> mode-select -> save-select -> job-select -> "
              "color-select -> name-entry...")
        press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A)); settle(c, 1.5)
        press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 1.5)
        press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 2.5)
        press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 2.5)
        press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 2.5)
        print(f"  DISPCNT=0x{read_dispcnt(c):04x} (expect 0x1e40)")

    raw = c.read_mem(DISPATCH_TABLE_ADDR, NUM_CATEGORIES * 4)
    import struct
    entries = struct.unpack(f"<{NUM_CATEGORIES}I", raw)

    print(f"\ncategory dispatch table @ IWRAM 0x{DISPATCH_TABLE_ADDR:08x} "
          f"(sampled at screen={args.screen}):")
    for i, e in enumerate(entries):
        if e == 0:
            print(f"  category {i:2d}: 0x00000000  (unused - no glyph pool wired)")
            continue
        rom_off = e - 0x08000000
        cand0 = rom_off + STRUCT_TO_PIXEL_OFFSET_CAT0
        cand = rom_off + STRUCT_TO_PIXEL_OFFSET
        print(f"  category {i:2d}: 0x{e:08x}  (struct @ ROM 0x{rom_off:06x}; "
              f"candidate pixel-table base = 0x{cand:06x} [cat!=0] / "
              f"0x{cand0:06x} [cat==0])")

    c.close()
    print("\ndone, connection closed.")


if __name__ == "__main__":
    main()

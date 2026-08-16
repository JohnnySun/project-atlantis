#!/usr/bin/env python3
"""Read-only(ish) recon (session 11): given the ROM address of ANY real
NUL-terminated OBJ-sentence string (session 8 format - see
extract_string_pool.py), force the job-select screen to render it instead
of its own "職業を選んでください" line, then capture the BIOS-copy enqueue
call's per-glyph source pointer (ROM file offset 0x08001154, session 7)
for every character in order.

Why this works / what it gives you: the job-select screen redraws its
sprite list every frame, and each redraw calls the string-walk function
(file offset 0x0800e8bc, session 8) with r0 pointing at the sentence to
render. Breaking at that function's entry and overwriting r0 right before
it executes makes the *same, already-working* rendering pipeline draw
whatever string you point it at - no need to find/reach the screen that
would naturally display that string. This is how session 11 got a second,
fully independent, zero-free-parameter address for category 4 without any
new navigation: two known corpus indices (16 and 18) both landed on
0x08491be4 / 0x08491ce4, exactly matching a predicted base of 0x4913e4
(also derived, independently, from the live category-dispatch table - see
dump_category_dispatch_table.py) plus idx*0x80.

Any string in the dialogue pool (0x499000-0x500000, scan with
scan_string_pools.py / extract_string_pool.py) can be used as --target,
not just category-4 examples - this is a general "resolve any rare
category's table base from real corpus data" technique, not category-4
specific.

Usage:
    python3 hijack_and_capture_glyph_sources.py --target 0x0849e42c \
        --num-codes 12
    # requires: mgba -g <rom> already running in the background (fresh
    # instance - kill any stray prior one first, mGBA's GDB stub does not
    # accept a second connection cleanly).

Writes nothing to the ROM file; only pokes emulator registers to inject
button presses and hijack r0, exactly like navigate_to_char_create.py /
trace_sentence_string_source.py.
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbstub_client import GdbClient  # noqa: E402

KEYINPUT = 0x04000130
DISPCNT = 0x04000000
NOTHING_PRESSED = 0x3FF
BTN_A = 0x01
BTN_START = 0x08

STRING_WALK_FUNC_ENTRY = 0x0800e8bc
ENQUEUE = 0x08001154
KNOWN_JOBSELECT_STR_PTR = 0x08499b1a  # "職業を選んでください" - session 8


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


def read_codes(rom_bytes, addr):
    """addr is a 0x08xxxxxx GBA address; rom_bytes indexed by file offset."""
    codes = []
    p = addr - 0x08000000
    while True:
        v = struct.unpack_from("<H", rom_bytes, p)[0]
        p += 2
        if v == 0:
            break
        codes.append(v)
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?",
                     default="games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--target", type=lambda x: int(x, 0), required=True,
                     help="0x08xxxxxx GBA address of the NUL-terminated code array to "
                          "force-render (a single line - use the exact line start, not "
                          "a multi-line pool entry's marker offset; see "
                          "extract_string_pool.py's walk_pool() to compute line starts "
                          "for marker>1 entries)")
    ap.add_argument("--num-codes", type=int, default=None,
                     help="how many codes to expect/capture (default: auto-read from ROM)")
    args = ap.parse_args()

    rom_bytes = open(args.rom, "rb").read()
    codes = read_codes(rom_bytes, args.target)
    if args.num_codes is None:
        args.num_codes = len(codes)
    print(f"target string @ 0x{args.target:08x}: {len(codes)} codes: "
          f"{[hex(c) for c in codes]}")

    c = GdbClient(args.host, args.port, timeout=8.0)
    print(f"connecting to {args.host}:{args.port} ...")
    c.connect()
    c.send("qSupported:multiprocess+")
    c.send("?")

    if not wait_for_dispcnt(c, 0x1240, timeout_s=20.0):
        print("TIMEOUT waiting for title screen.")
        sys.exit(2)
    settle(c, 4.0)
    print("Navigating: title -> mode-select -> save-select -> job-select...")
    press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A)); settle(c, 1.5)
    press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 1.5)
    press_button(c, NOTHING_PRESSED & ~BTN_A); settle(c, 2.5)
    print(f"  job-select DISPCNT=0x{read_dispcnt(c):04x}")

    print(f"Arming breakpoint at string-walk entry 0x{STRING_WALK_FUNC_ENTRY:08x}, "
          f"waiting for the known job-select string ptr 0x{KNOWN_JOBSELECT_STR_PTR:08x}...")
    c.set_breakpoint(STRING_WALK_FUNC_ENTRY, kind=2, wtype=1)
    hijacked = False
    for i in range(200):
        c.cont_and_wait(timeout=10.0)
        regs = c.read_registers()
        if regs[15] != STRING_WALK_FUNC_ENTRY:
            c.send("s")
            continue
        if regs[0] == KNOWN_JOBSELECT_STR_PTR:
            print(f"  hit#{i}: hijacking r0 -> 0x{args.target:08x}")
            c.write_register(0, args.target)
            hijacked = True
            break
        c.send("s")
    c.remove_breakpoint(STRING_WALK_FUNC_ENTRY, kind=2, wtype=1)
    if not hijacked:
        print("[FAIL] never saw the known job-select string pointer.")
        c.close()
        sys.exit(3)

    print(f"Arming breakpoint at enqueue call 0x{ENQUEUE:08x} to capture per-glyph "
          f"source pointers (expect {args.num_codes} hits)...")
    c.set_breakpoint(ENQUEUE, kind=2, wtype=1)
    captured = []
    try:
        for i in range(args.num_codes * 4 + 10):
            if len(captured) >= args.num_codes:
                break
            c.cont_and_wait(timeout=10.0)
            regs = c.read_registers()
            if regs[15] != ENQUEUE:
                c.send("s")
                continue
            captured.append(regs[0])
            c.send("s")
    finally:
        c.remove_breakpoint(ENQUEUE, kind=2, wtype=1)

    print(f"\nCaptured {len(captured)} enqueue source pointers:")
    for i, addr in enumerate(captured):
        code = codes[i] if i < len(codes) else None
        if code is not None:
            cat = (code >> 8) & 0xF
            idx = (code & 0xFF) - 1
            print(f"  [{i}] code=0x{code:04x} category={cat:2d} idx={idx:3d}  ->  r0=0x{addr:08x}")
        else:
            print(f"  [{i}] (no matching code)  ->  r0=0x{addr:08x}")

    c.close()
    print("\ndone, connection closed.")


if __name__ == "__main__":
    main()

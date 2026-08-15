#!/usr/bin/env python3
"""Read-only(ish) recon (session 8): find and decode the actual in-ROM
character-code array behind an OBJ-rendered sentence (e.g. job-select's
"職業を選んでください"), closing the gap session 7 left open ("index*0x80
formula found, but no idea where the per-character index sequence itself
is stored").

Method: break at the entry of the innermost per-character "draw one
glyph" function, walk *up* the call chain by breaking successively
higher, until reaching a function whose incoming r0 argument is a
pointer to a NUL-terminated array of 16-bit codes read with `ldrh`/+2
stride - a real string. Concretely (see
research/obj-sentence-string-format.md for the full derivation):

  ROM file offset 0x080034d0 (bl 0x8001154): known from session 7, the
  BIOS-copy enqueue call, one hit per visible sprite.
  -> its caller, ROM file offset 0x08003310: a generic "instantiate one
     sprite-group by (category r1, index r3)" routine; r3 argument here
     turned out to be exactly (this session's finding) the glyph's
     entry-index minus 0 offset used elsewhere, i.e. NOT the raw
     source data - one more level up needed.
  -> ITS caller, ROM file offset 0x0800e924 (inside a function starting
     at file offset 0x0800e8bc): computes r3 = (byte_from_r2 & 0xff) - 1
     and r1 = *(table[(r2>>6)&0x3c]) from a 16-bit value r2, read one
     per loop iteration via `ldrh r2,[r5]; ...; adds r5,#2` with r5
     walking until a 0x0000 terminator - THIS is the real string walk.
     r5's initial value equals this function's own r0 argument.

This script breaks at that function's entry (file offset 0x0800e8bc) on
both the job-select ("職業を選んでください") and color-select ("色を
選んでください") screens, reports the r0 string-pointer address, dumps
the halfwords there, and decodes each code as
    category = (code >> 8) & 0xF     (font/glyph-pool selector)
    glyph_entry_index = (code & 0xFF) - 1
and cross-checks glyph_entry_index against the known session 5/6/7
gojuon-order indices for the hiragana in each sentence (category 0 codes
only - kanji use categories 2/3, whose own indexing this session did not
fully resolve, see the research doc).

Usage:
    python3 trace_sentence_string_source.py --screen job-select
    python3 trace_sentence_string_source.py --screen color-select
    # requires: mgba -g <rom> already running in the background (fresh
    # instance - kill any stray prior one first, mGBA's GDB stub does
    # not accept a second connection cleanly).

Writes nothing to the ROM file; only pokes emulator registers/memory to
inject button presses and set breakpoints, exactly like
navigate_to_char_create.py / trace_sentence_glyph_load.py.
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

STRING_WALK_FUNC_ENTRY = 0x0800e8bc

# Session 5/6/7-confirmed gojuon-order glyph_entry_index values (=
# char_idx + 1 - see research/obj-sentence-string-format.md "entry_index
# vs. char_idx offset") for kana glyphs that appear in these two prompts
# (category-0 codes only; kanji glyph_idx values are recorded but not
# independently cross-checked here - see research doc "漢字定址機制仍未解").
KNOWN_KANA_INDEX = {
    2: "い", 8: "く", 11: "さ", 45: "を", 46: "ん", 57: "だ", 60: "で",
}


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
            c.cont_and_wait(timeout=per_hit_timeout)
            value = mask_to_hold if i < hold_frames else NOTHING_PRESSED
            c.write_register(dest_reg, value)
    finally:
        c.remove_watchpoint(KEYINPUT, kind=2, wtype=3)


def decode_string(rom_addr: int, halfwords):
    codes = []
    for hw in halfwords:
        if hw == 0:
            break
        category = (hw >> 8) & 0xF
        glyph_idx = (hw & 0xFF) - 1
        label = KNOWN_KANA_INDEX.get(glyph_idx, "?") if category == 0 else "(kanji pool)"
        codes.append((hw, category, glyph_idx, label))
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--screen", choices=["job-select", "color-select"], default="job-select")
    ap.add_argument("--max-hits", type=int, default=6)
    args = ap.parse_args()

    c = GdbClient(args.host, args.port, timeout=8.0)
    print(f"connecting to {args.host}:{args.port} ...")
    c.connect()
    c.send("qSupported:multiprocess+")
    c.send("?")

    print("Navigating: title -> mode-select -> save-select -> job-select...")
    if not wait_for_dispcnt(c, 0x1240, timeout_s=20.0):
        print("TIMEOUT waiting for title screen. Aborting.")
        sys.exit(2)
    settle(c, 4.0)
    press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A), poll_pc=0x0800077a)
    settle(c, 1.5)
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)  # mode-select
    settle(c, 1.5)
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)  # save-select FILE1 -> job-select
    settle(c, 2.5)
    print(f"  job-select DISPCNT=0x{read_dispcnt(c):04x}")

    if args.screen == "color-select":
        print("Advancing one more screen: job-select -> color-select...")
        press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
        settle(c, 2.5)
        print(f"  color-select DISPCNT=0x{read_dispcnt(c):04x}")

    print(f"Arming breakpoint at 0x{STRING_WALK_FUNC_ENTRY:08x} "
          "(the string-walk function's entry point; its r0 argument is "
          "the sentence string pointer)...")
    c.set_breakpoint(STRING_WALK_FUNC_ENTRY, kind=2, wtype=1)
    found = False
    try:
        for i in range(args.max_hits):
            c.cont_and_wait(timeout=10.0)
            regs = c.read_registers()
            pc = regs[15]
            if pc != STRING_WALK_FUNC_ENTRY:
                c.send("s")
                continue
            r0, r2 = regs[0], regs[2]
            raw = c.read_mem(r0, 40)
            hw = [int.from_bytes(raw[j:j + 2], "little") for j in range(0, 40, 2)]
            codes = decode_string(r0, hw)
            if len(codes) >= 5:  # the sentence call, not a short 1-2 char label
                found = True
                print(f"\n  hit#{i}: string pointer r0=0x{r0:08x} (category-select r2=0x{r2:08x})")
                print(f"  raw halfwords: {[hex(x) for x in hw[:len(codes) + 1]]}")
                print(f"  decoded ({len(codes)} chars):")
                for hwv, cat, idx, label in codes:
                    print(f"    0x{hwv:04x} -> category={cat} glyph_entry_index={idx} "
                          f"{'known-kana='+label if label not in ('?','(kanji pool)') else label}")
                break
            c.send("s")
    finally:
        c.remove_breakpoint(STRING_WALK_FUNC_ENTRY, kind=2, wtype=1)

    if not found:
        print(f"\n[warn] did not see a >=5-char string within {args.max_hits} hits - "
              "the sentence call may not have fired yet in this window, try "
              "increasing --max-hits.")

    c.close()
    print("\ndone, connection closed.")


if __name__ == "__main__":
    main()

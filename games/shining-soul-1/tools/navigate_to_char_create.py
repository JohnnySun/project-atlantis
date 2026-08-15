#!/usr/bin/env python3
"""Read-only(ish) recon (written session 5, verified + completed session 6):
extend navigate_and_dump.py's title -> mode-select -> save-select recipe
into the new-game / character-creation flow reached by selecting "FILE 1"
on the save-select screen.

Session 5 wrote this script and got as far as steps 1-5 (through
"05_after_second_a") but never verified the result or ran step 6 - its
dumps sat unreviewed in research/session5_tmp/. Session 6 reproduced the
whole flow from a clean mGBA boot (independent of any session-5 leftover
state) and confirmed steps 1-5 render the SAME screens session 5's
unverified dumps showed, then completed step 6 for the first time.
Confirmed screen sequence (see README "第五輪偵察" and
research/name-entry-hiragana-codepage.md for full detail, including a
DISPCNT/BGxCNT table per screen):
    01 title -> 02 mode-select -> 03 save-select -> 04 job-select
    ("剣士"/"職業を選んでください") -> 05 color-select
    ("カラー1"/"色を選んでください") -> 06 name-entry (a full BG1
    hiragana input-grid keyboard, backed by a SECOND, newly-located
    1024-tile BG font table at ROM 0x1316e8-0x1396e8, distinct from the
    session-4-confirmed UI table at 0x1398e8 - both get loaded into the
    same VRAM charbase-0 address on different screens, so charbase 0 is
    NOT a fixed global table, contrary to session 4's implicit
    assumption).

Reuses the exact key-injection technique validated in session 3/4
(read watchpoint on KEYINPUT + register overwrite - see README "第三輪
偵察" "根因確認" for why writing KEYINPUT memory directly does NOT
work). This is the only tool in this game's toolset (besides
navigate_and_dump.py) that writes emulator state, and it never writes
the ROM file itself.

Usage:
    python3 navigate_to_char_create.py --out-dir /tmp/ss1_dump2
    # requires: /opt/homebrew/bin/mgba -g <rom> already running in the
    # background (kill any stray prior instance first - mGBA's GDB stub
    # does not accept a second connection cleanly).
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
PALETTE = 0x05000000
OAM = 0x07000000

NOTHING_PRESSED = 0x3FF
BTN_A = 0x01
BTN_B = 0x02
BTN_START = 0x08
BTN_UP = 0x40
BTN_DOWN = 0x80


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


def press_button(c, mask_to_hold, hold_frames=28, release_frames=6,
                  per_hit_timeout=10.0, dest_reg=1, poll_pc=None):
    c.set_watchpoint(KEYINPUT, kind=2, wtype=3)  # read watchpoint, halfword
    try:
        seen_pcs = set()
        total = hold_frames + release_frames
        for i in range(total):
            stop = c.cont_and_wait(timeout=per_hit_timeout)
            kind, addr = parse_stop_watch(stop)
            if kind is None:
                print(f"  [warn] hit {i}: non-watch stop packet: {stop!r}")
            regs = c.read_registers()
            pc = regs[15]
            seen_pcs.add(pc)
            if poll_pc is not None and pc != poll_pc and i == 0:
                print(f"  [note] first hit pc=0x{pc:08x} (expected 0x{poll_pc:08x}) "
                      f"- proceeding anyway, may be an early boot-time read")
            value = mask_to_hold if i < hold_frames else NOTHING_PRESSED
            c.write_register(dest_reg, value)
        print(f"  press_button done, saw PCs: {[hex(p) for p in seen_pcs]}")
    finally:
        c.remove_watchpoint(KEYINPUT, kind=2, wtype=3)


def dump_layer_state(c, out_dir, tag):
    os.makedirs(out_dir, exist_ok=True)
    dispcnt = read_dispcnt(c)
    bg_cnts = {}
    for i in range(4):
        addr = 0x04000008 + i * 2
        bg_cnts[i] = int.from_bytes(c.read_mem(addr, 2), "little")
    vram = c.read_mem(VRAM, 0x18000)
    pal = c.read_mem(PALETTE, 0x400)
    oam = c.read_mem(OAM, 0x400)
    with open(os.path.join(out_dir, f"{tag}.vram.bin"), "wb") as f:
        f.write(vram)
    with open(os.path.join(out_dir, f"{tag}.pal.bin"), "wb") as f:
        f.write(pal)
    with open(os.path.join(out_dir, f"{tag}.oam.bin"), "wb") as f:
        f.write(oam)
    with open(os.path.join(out_dir, f"{tag}.regs.txt"), "w") as f:
        f.write(f"DISPCNT=0x{dispcnt:04x}\n")
        for i in range(4):
            f.write(f"BG{i}CNT=0x{bg_cnts[i]:04x}\n")
    print(f"  dumped {tag}: DISPCNT=0x{dispcnt:04x} BGCNT={ {k: hex(v) for k,v in bg_cnts.items()} }")
    return dispcnt, bg_cnts


def settle(c, seconds):
    c.cont()
    time.sleep(seconds)
    c.interrupt()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    c = GdbClient(args.host, args.port, timeout=8.0)
    print(f"connecting to {args.host}:{args.port} ...")
    c.connect()
    print("qSupported:", c.send("qSupported:multiprocess+"))
    print("?:", c.send("?"))

    print("Step 1: free-run to stable title screen (DISPCNT==0x1240)...")
    if not wait_for_dispcnt(c, 0x1240, timeout_s=20.0):
        print("TIMEOUT: never saw title-screen DISPCNT. Aborting (not hanging).")
        sys.exit(2)
    print("  margin free-run (session 4 lesson: DISPCNT hitting the target "
          "value transiently does not mean the screen is stable/input-ready)...")
    settle(c, 4.0)
    dump_layer_state(c, args.out_dir, "01_title")

    print("Step 2: press Start+A to leave title -> mode-select...")
    press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A), poll_pc=0x0800077a)
    settle(c, 1.5)
    dump_layer_state(c, args.out_dir, "02_mode_select")

    print("Step 3: press A to confirm single-player mode -> save-select...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 1.5)
    dispcnt, bgcnt = dump_layer_state(c, args.out_dir, "03_save_select")
    if dispcnt != 0x1d40:
        print(f"[warn] DISPCNT=0x{dispcnt:04x}, expected 0x1d40 for save-select - "
              f"continuing anyway but next step may land somewhere unexpected.")

    print("Step 4: press A to select FILE 1 (default cursor position)...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    print("  free-running 2.5s margin to let any transition/animation settle...")
    settle(c, 2.5)
    dispcnt4, bgcnt4 = dump_layer_state(c, args.out_dir, "04_after_file1_a")

    print("Step 5: press A again in case FILE 1 needed a confirm dialog "
          "('empty slot -> create new game?' is a common pattern)...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 2.5)
    dispcnt5, bgcnt5 = dump_layer_state(c, args.out_dir, "05_after_second_a")

    print("Step 6: press A a third time - confirmed (session 6) to reach the "
          "name-entry screen: a full BG1 hiragana input-grid keyboard backed "
          "by a second BG font table at ROM 0x1316e8, distinct from the "
          "0x1398e8 UI table used by steps 3-5. See "
          "research/name-entry-hiragana-codepage.md for the full codepage "
          "extracted from this screen...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 2.5)
    dispcnt6, bgcnt6 = dump_layer_state(c, args.out_dir, "06_after_third_a")

    c.close()
    print("done, connection closed.")
    print(f"Summary: 03={hex(dispcnt)} 04={hex(dispcnt4)} 05={hex(dispcnt5)} 06={hex(dispcnt6)}")


if __name__ == "__main__":
    main()

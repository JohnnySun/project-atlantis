#!/usr/bin/env python3
"""Read-only(ish) recon: drive the emulator from boot to the save-file-
select screen using the read-watchpoint + register-overwrite key
injection technique session 3 validated (see README "第三輪偵察"), then
dump VRAM/palette/OAM to files for offline rendering/analysis.

This is the ONLY tool in this game's toolset that writes emulator state
(via gdbstub_client.write_register / set_watchpoint) - it never writes
the ROM file itself. It exists because session 3's navigation recipe was
described in prose in the README but not saved as a reusable script;
session 4 needs to reach the same screen repeatably to read the BG2/BG3
tilemap tile-index arrays, so this codifies that recipe instead of
re-deriving it by hand each time.

Recipe (session 3, confirmed against mGBA 0.10.5 source - writing
KEYINPUT memory directly does NOT work, see README "根因確認"):
  1. Free-run until DISPCNT == 0x1240 (stable title screen, BG1+OBJ).
  2. Set a READ watchpoint on KEYINPUT (0x04000130). The shared per-frame
     input-poll routine hits this at a fixed PC (0x0800077a in this
     build) on every screen from the title onward.
  3. On each hit, overwrite the destination register (r1 in this build)
     with the desired "pressed" bitmask (active-low, 10 bits, "nothing
     pressed" = 0x3FF) for ~20-30 consecutive frames, then release
     (write back 0x3FF) for a few more frames to produce a clean
     press+release edge.
  4. Free-run a bit to let the game process the transition, then repeat
     for the next screen.

Every blocking wait (cont_and_wait) uses an explicit timeout and raises
TimeoutError rather than hanging silently - if that happens this script
prints where it got stuck and exits non-zero instead of blocking.

Usage:
    python3 navigate_and_dump.py --out-dir /tmp/ss1_dump
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
BTN_START = 0x08


def read_dispcnt(c):
    return int.from_bytes(c.read_mem(DISPCNT, 2), "little")


def wait_for_dispcnt(c, target, timeout_s=20.0, poll_chunk=1.0):
    """Free-run in short bursts, checking DISPCNT after each, until it
    matches `target` or timeout_s elapses (wall clock)."""
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
    """Set a read watchpoint on KEYINPUT, catch the shared poll routine
    hitting it, and overwrite dest_reg with mask_to_hold (active-low
    'pressed' value) for hold_frames hits, then NOTHING_PRESSED for
    release_frames hits. Removes the watchpoint before returning.

    Raises TimeoutError (does not hang) if a hit doesn't arrive within
    per_hit_timeout seconds.
    """
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
            # NOTE: deliberately no single-step here. README session-3 notes
            # explicitly call out that the KEYINPUT case is the one
            # *exception* where repeated hits at the same PC without an
            # intervening single-step are expected/correct, because PC has
            # already advanced past the read (each hit is a new frame's
            # poll) - single-stepping here just wastes an instruction and
            # was found empirically NOT to be needed for this watchpoint.
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
    print("  holding a further ~4s free-run margin so title is truly stable "
          "(session 3 found DISPCNT can read 0x1240 transiently before the "
          "screen is actually accepting input)...")
    c.cont()
    time.sleep(4.0)
    c.interrupt()
    val = read_dispcnt(c)
    print(f"  DISPCNT after margin=0x{val:04x}")
    dump_layer_state(c, args.out_dir, "01_title")

    print("Step 2: press Start+A to leave title -> mode-select...")
    press_button(c, NOTHING_PRESSED & ~(BTN_START | BTN_A), poll_pc=0x0800077a)
    print("  free-running 1.5s to let transition settle...")
    c.cont()
    time.sleep(1.5)
    c.interrupt()
    dump_layer_state(c, args.out_dir, "02_mode_select")

    print("Step 3: press A to confirm single-player mode -> save-select...")
    press_button(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    print("  free-running 1.5s to let transition settle...")
    c.cont()
    time.sleep(1.5)
    c.interrupt()
    dispcnt, bgcnt = dump_layer_state(c, args.out_dir, "03_save_select")

    if dispcnt == 0x1d40:
        print("Reached save-select screen (DISPCNT==0x1d40 as session 3 documented).")
    else:
        print(f"[warn] DISPCNT=0x{dispcnt:04x}, expected 0x1d40 for save-select - "
              f"may need another press or may already be there via a different route; "
              f"inspect dumped VRAM/OAM manually.")

    c.close()
    print("done, connection closed.")


if __name__ == "__main__":
    main()

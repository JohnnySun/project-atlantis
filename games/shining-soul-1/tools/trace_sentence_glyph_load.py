#!/usr/bin/env python3
"""Read-only(ish) recon (session 7): find the code that copies the
job-select screen's OBJ-rendered sentence glyphs ("職業を選んでください")
from ROM into VRAM, and inspect whether that path shows any sign of a
character-code -> glyph-address lookup (a real text-rendering engine)
versus a bespoke per-screen blit.

Session 6 located the ROM source bytes for all 10 glyphs of this sentence
(research/name-entry-hiragana-codepage.md, "附帶發現" section) but did not
find the loader code. Session 3 found the *generic* VRAM-transfer queue
(ROM file offset ~0x11a0-0x1220, flushing entries via BIOS CpuSet/
CpuFastSet wrapper stubs at file offset 0x503bc/0x503c0) that moves the
save-select screen's BG font table into VRAM, and tested one enqueue-
function candidate (file offset 0x1154) which did NOT show font-range
source pointers in ~550 generic idle-frame intercepts - but never tested
during an actual font-loading transition (only during steady-state idle
screens). This script targets that gap directly: it arms watchpoints
*during the exact save-select -> job-select transition frame* (the one
button press that causes the sentence glyphs to first appear), which is
the one moment session 3 never captured.

Method (per this session's task): set a WRITE watchpoint on the known
VRAM destination of the sentence's first glyph tile ("職" -> VRAM
0x06010320, OBJ tile #25) *before* pressing A on save-select's FILE 1,
then dual-watch that address alongside the usual KEYINPUT read
watchpoint used for button injection (see navigate_to_char_create.py).
Every hit's PC/LR/r0-r3 are recorded. As a secondary/fallback technique
matching session 3's *actual* successful method (a write watchpoint on
the VRAM destination risks aliasing with an unrelated subsystem reusing
the same tile slot, as session 3 discovered with the cloud-animation
false lead at VRAM 0x06010000) this script can also re-arm a READ
watchpoint on the ROM source address of a chosen glyph instead
(--watch-mode rom-read), which is more surgical since ROM source
addresses for glyph data are not reused by anything else.

Usage:
    python3 trace_sentence_glyph_load.py --watch-mode vram-write
    python3 trace_sentence_glyph_load.py --watch-mode rom-read --glyph 職
    # requires: mgba -g <rom> already running in the background.

Writes nothing to the ROM file; only pokes emulator registers/memory to
inject button presses, exactly like navigate_to_char_create.py.
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

# Session 6-confirmed ROM source addresses (file offset) and VRAM
# destination OBJ tile numbers for each glyph of "職業を選んでください"
# (research/name-entry-hiragana-codepage.md). VRAM tile addr = VRAM +
# 0x10000 (OBJ charblock 4) + tile# * 32.
GLYPHS = {
    "職": (0x482424, 25),
    "業": (0x48eec4, 29),
    "を": (0x46c1e4, 33),
    "選": (0x487fc4, 37),
    "ん": (0x46c264, 41),
    "で": (0x46c964, 45),
    "く": (0x46af64, 49),
    "だ": (0x46c7e4, 53),
    "さ": (0x46b0e4, 57),
    "い": (0x46ac64, 61),
}

# Session 3-confirmed generic transfer-queue landmarks (file offsets).
QUEUE_LOOP_LO = 0x1140
QUEUE_LOOP_HI = 0x1220
CPUFASTSET_WRAPPER = 0x503bc
CPUSET_WRAPPER = 0x503c0
ENQUEUE_CANDIDATE_REJECTED = 0x1154  # session 3: tested, no font hits


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


def simple_press(c, mask_to_hold, hold_frames=28, release_frames=6,
                  per_hit_timeout=10.0, dest_reg=1, poll_pc=None):
    """Plain button press (no extra watch) - used for steps 1-3, identical
    technique to navigate_to_char_create.py's press_button()."""
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


def press_and_catch(c, mask_to_hold, catch_addr, catch_kind, catch_wtype,
                     hold_frames=40, release_frames=10, per_hit_timeout=15.0,
                     dest_reg=1, max_hits=40, max_iterations=4000):
    """Inject a button press (KEYINPUT read-watch technique) while a SECOND
    watchpoint (catch_addr/catch_kind/catch_wtype) is simultaneously armed.
    Every hit on catch_addr is recorded (pc, lr, r0-r3, raw stop packet)
    and the target is single-stepped past it so a tight copy loop touching
    the same address repeatedly doesn't get stuck reporting the same PC
    forever. Returns the list of catch-hits."""
    c.set_watchpoint(KEYINPUT, kind=2, wtype=3)
    c.set_watchpoint(catch_addr, kind=catch_kind, wtype=catch_wtype)
    hits = []
    frame = 0
    iterations = 0
    total = hold_frames + release_frames
    try:
        while frame < total and iterations < max_iterations and len(hits) < max_hits:
            iterations += 1
            stop = c.cont_and_wait(timeout=per_hit_timeout)
            kind, addr = parse_stop_watch(stop)
            regs = c.read_registers()
            pc, lr = regs[15], regs[14]
            if addr == catch_addr:
                hits.append({
                    "pc": pc, "lr": lr,
                    "r0": regs[0], "r1": regs[1], "r2": regs[2], "r3": regs[3],
                    "r4": regs[4],
                    "stop": stop,
                })
                print(f"  [CATCH #{len(hits)}] pc=0x{pc:08x} lr=0x{lr:08x} "
                      f"r0=0x{regs[0]:08x} r1=0x{regs[1]:08x} r2=0x{regs[2]:08x} "
                      f"r3=0x{regs[3]:08x}")
                c.send("s")  # step past so we don't re-hit the same instruction forever
                continue
            elif addr == KEYINPUT:
                value = mask_to_hold if frame < hold_frames else NOTHING_PRESSED
                c.write_register(dest_reg, value)
                frame += 1
            else:
                print(f"  [warn] unexpected watch addr=0x{addr if addr else 0:08x} "
                      f"pc=0x{pc:08x} - single-stepping past")
                c.send("s")
        if iterations >= max_iterations:
            print("  [warn] hit max_iterations safety cap, stopping")
    finally:
        c.remove_watchpoint(KEYINPUT, kind=2, wtype=3)
        c.remove_watchpoint(catch_addr, kind=catch_kind, wtype=catch_wtype)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--watch-mode", choices=["vram-write", "rom-read"], default="vram-write")
    ap.add_argument("--glyph", default="職", choices=list(GLYPHS.keys()))
    ap.add_argument("--kind", type=int, default=1, help="watchpoint byte-width (default 1=byte, most sensitive)")
    ap.add_argument("--out-dir", default="/tmp/ss1_trace_font")
    args = ap.parse_args()

    rom_off, tile = GLYPHS[args.glyph]
    vram_dest = VRAM + 0x10000 + tile * 32
    rom_src = 0x08000000 + rom_off

    if args.watch_mode == "vram-write":
        catch_addr, catch_wtype, mode_desc = vram_dest, 2, f"WRITE watch on VRAM dest 0x{vram_dest:08x} (glyph {args.glyph}, tile#{tile})"
    else:
        catch_addr, catch_wtype, mode_desc = rom_src, 3, f"READ watch on ROM source 0x{rom_src:08x} (glyph {args.glyph})"

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
    simple_press(c, NOTHING_PRESSED & ~(BTN_START | BTN_A), poll_pc=0x0800077a)
    settle(c, 1.5)

    print("Step 3: press A to confirm single-player mode -> save-select...")
    simple_press(c, NOTHING_PRESSED & ~BTN_A, poll_pc=0x0800077a)
    settle(c, 1.5)
    dispcnt = read_dispcnt(c)
    print(f"  save-select DISPCNT=0x{dispcnt:04x} (want 0x1d40)")

    print(f"Step 4: arming {mode_desc}")
    print("  then pressing A to select FILE 1 -> triggers job-select transition "
          "(this is the moment the sentence glyphs first get drawn)...")
    hits = press_and_catch(c, NOTHING_PRESSED & ~BTN_A, catch_addr,
                            args.kind, catch_wtype,
                            hold_frames=40, release_frames=20)

    print(f"\nTotal catches: {len(hits)}")
    with open(os.path.join(args.out_dir, f"hits_{args.watch_mode}_{args.glyph}.txt"), "w") as f:
        f.write(f"mode: {mode_desc}\n")
        for h in hits:
            f.write(f"pc=0x{h['pc']:08x} lr=0x{h['lr']:08x} "
                     f"r0=0x{h['r0']:08x} r1=0x{h['r1']:08x} r2=0x{h['r2']:08x} "
                     f"r3=0x{h['r3']:08x} r4=0x{h['r4']:08x}\n")

    print("\nSettling + dumping post-transition screen state for sanity check...")
    settle(c, 2.5)
    dispcnt_after = read_dispcnt(c)
    vram = c.read_mem(VRAM, 0x18000)
    pal = c.read_mem(PALETTE, 0x400)
    oam = c.read_mem(OAM, 0x400)
    with open(os.path.join(args.out_dir, "post.vram.bin"), "wb") as f:
        f.write(vram)
    with open(os.path.join(args.out_dir, "post.pal.bin"), "wb") as f:
        f.write(pal)
    with open(os.path.join(args.out_dir, "post.oam.bin"), "wb") as f:
        f.write(oam)
    print(f"  post-transition DISPCNT=0x{dispcnt_after:04x}")

    c.close()
    print("done, connection closed.")


if __name__ == "__main__":
    main()

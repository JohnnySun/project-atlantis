#!/usr/bin/env python3
"""Read-only recon: disassemble around THUMB `swi` (BIOS call) candidate
offsets found by scan_swi_calls.py, using capstone, to (a) confirm which
candidates are real instructions reached by a plausible instruction
stream (vs misaligned/data false positives) and (b) trace backward for
the r0 (source) / r1 (dest) / r2 register values set up before each
compression-related BIOS call (swi 0x10-0x18), resolving THUMB
`ldr rX, [pc, #imm]` literal-pool loads back to their constant value.

This is still a heuristic, not a full data-flow analysis:
  - "Confirmed" here means: walking forward from a nearby detected
    function prologue (`push {..., lr}`) or a fixed lookback window,
    capstone decodes a clean, error-free instruction stream that lands
    exactly on the candidate offset with mnemonic `svc`. It does NOT
    prove the code path is reachable/executed at runtime.
  - Register tracing only follows simple `mov r,#imm`, `ldr r,[pc,#imm]`
    (literal pool), and `mov r,r` copies within the local window. `add`/
    `sub` adjustments, register-relative loads, and cross-function
    argument setup (r0/r1 set by caller, not visible in this window) are
    NOT modeled - a "not found" result means "not found by this simple
    heuristic in-window", not "does not exist".
  - GBA ROM file offset X maps 1:1 to CPU address 0x08000000 + X (ROM is
    memory-mapped there); this script assumes that mapping throughout.

Usage:
  python3 disasm_swi_calls.py <rom.gba> [--imm 0x10,0x11,...] [--window 64]
"""
import argparse
import struct
from collections import Counter

try:
    import capstone
except ImportError:
    raise SystemExit(
        "capstone not importable under this interpreter - "
        "on this machine use /usr/bin/python3, not /opt/homebrew/bin/python3"
    )

ROM_BASE = 0x08000000

SWI_NAMES = {
    0x10: "BitUnPack", 0x11: "LZ77UnCompWram", 0x12: "LZ77UnCompVram",
    0x13: "HuffUnComp", 0x14: "RLUnCompWram", 0x15: "RLUnCompVram",
    0x16: "Diff8bitUnFilterWram", 0x17: "Diff8bitUnFilterVram",
    0x18: "Diff16bitUnFilter",
}

MEM_REGIONS = [
    (0x08000000, 0x0A000000, "ROM"),
    (0x02000000, 0x02040000, "EWRAM"),
    (0x03000000, 0x03008000, "IWRAM"),
    (0x05000000, 0x05000400, "PALETTE"),
    (0x06000000, 0x06018000, "VRAM"),
    (0x07000000, 0x07000400, "OAM"),
]


def classify_addr(addr):
    for lo, hi, name in MEM_REGIONS:
        if lo <= addr < hi:
            return name
    return "?"


def find_swi_offsets(data, imms):
    locs = {imm: [] for imm in imms}
    n = len(data)
    for off in range(0, n - 1, 2):
        if data[off + 1] == 0xDF and data[off] in locs:
            locs[data[off]].append(off)
    return locs


def find_prologue_start(data, swi_off, max_back=400):
    """Scan backward for the nearest THUMB push{...,lr} (0xB5xx) or
    push{...} (0xB4xx) halfword, as a plausible function-start anchor."""
    lo = max(0, swi_off - max_back)
    for off in range(swi_off - 2, lo - 2, -2):
        if off < 0:
            break
        b1 = data[off + 1]
        if b1 in (0xB5, 0xB4):  # push instructions
            return off
    return None


def disasm_window(md, data, start, end):
    """Disassemble data[start:end] (must be halfword-aligned), return
    list of capstone insns with .address already offset by ROM_BASE."""
    code = data[start:end]
    insns = list(md.disasm(code, ROM_BASE + start))
    return insns


def resolve_pc_literal(data, insn):
    """For `ldr rX, [pc, #imm]`, compute the literal pool file offset and
    read the 32-bit LE word. THUMB PC for this addressing mode is
    (insn_addr + 4) & ~3 + imm. Returns (pool_addr, value) or None."""
    if insn.mnemonic != "ldr":
        return None
    ops = insn.operands
    if len(ops) != 2:
        return None
    mem = ops[1]
    if mem.type != capstone.arm.ARM_OP_MEM:
        return None
    if mem.mem.base != capstone.arm.ARM_REG_PC:
        return None
    imm = mem.mem.disp
    pc = (insn.address + 4) & ~3
    pool_addr = pc + imm
    pool_off = pool_addr - ROM_BASE
    if pool_off < 0 or pool_off + 4 > len(data):
        return None
    value = struct.unpack_from("<I", data, pool_off)[0]
    return pool_addr, value


REG_NAMES = {f"r{i}": i for i in range(13)}
REG_NAMES.update({"sp": 13, "lr": 14, "pc": 15})


def trace_register(insns, swi_index, want_reg, data):
    """Walk backward from swi_index-1 looking for the most recent
    instruction that sets `want_reg` (e.g. 'r0'). Returns a description
    string or None."""
    for i in range(swi_index - 1, max(-1, swi_index - 30), -1):
        insn = insns[i]
        ops_str = insn.op_str
        mnem = insn.mnemonic
        # crude: only handle instructions whose first operand is exactly want_reg
        first_op = ops_str.split(",")[0].strip() if ops_str else ""
        if first_op != want_reg:
            continue
        if mnem == "movs" or mnem == "mov":
            return f"{mnem} {ops_str}  @0x{insn.address:x}"
        if mnem == "ldr":
            lit = resolve_pc_literal(data, insn)
            if lit:
                pool_addr, value = lit
                region = classify_addr(value)
                return (f"ldr {ops_str}  @0x{insn.address:x}  "
                        f"-> pool[0x{pool_addr:x}] = 0x{value:08x} ({region})")
            return f"ldr {ops_str}  @0x{insn.address:x}  (non-pc-relative, not resolved)"
        if mnem in ("add", "sub", "mov"):
            return f"{mnem} {ops_str}  @0x{insn.address:x}  (not fully resolved: register arithmetic)"
        # any other write to want_reg we don't model
        return f"{mnem} {ops_str}  @0x{insn.address:x}  (unmodeled instruction)"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--imm", default="0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18",
                     help="comma-separated swi immediates to analyze")
    ap.add_argument("--window", type=int, default=400,
                     help="max bytes to look backward for a prologue anchor")
    ap.add_argument("--limit", type=int, default=1000,
                     help="max candidates per swi immediate to process")
    args = ap.parse_args()

    imms = [int(x, 0) for x in args.imm.split(",")]
    data = open(args.rom, "rb").read()

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True

    locs = find_swi_offsets(data, imms)

    summary = Counter()
    for imm in imms:
        name = SWI_NAMES.get(imm, f"swi_0x{imm:02x}")
        offsets = locs[imm][: args.limit]
        print(f"=== swi 0x{imm:02x} ({name}): {len(locs[imm])} raw candidates"
              f" (showing up to {len(offsets)}) ===")
        for swi_off in offsets:
            anchor = find_prologue_start(data, swi_off, args.window)
            start = anchor if anchor is not None else max(0, swi_off - args.window)
            # decode forward; capstone stops cleanly at invalid opcodes
            insns = disasm_window(md, data, start, swi_off + 2)
            if not insns:
                summary["no_decode"] += 1
                continue
            last = insns[-1]
            if last.address != ROM_BASE + swi_off or last.mnemonic != "svc":
                summary["misaligned_or_not_swi"] += 1
                continue
            # confirmed: clean decode lands exactly on svc at expected addr
            summary["confirmed"] += 1
            swi_index = len(insns) - 1
            r0 = trace_register(insns, swi_index, "r0", data)
            r1 = trace_register(insns, swi_index, "r1", data)
            r2 = trace_register(insns, swi_index, "r2", data) if imm == 0x10 else None
            anchor_str = f"anchor=0x{ROM_BASE+anchor:x}" if anchor is not None else "anchor=none(fixed-window)"
            print(f"  swi@0x{ROM_BASE+swi_off:x} ({anchor_str}, {len(insns)} insns decoded)")
            print(f"    r0: {r0}")
            print(f"    r1: {r1}")
            if imm == 0x10:
                print(f"    r2: {r2}")
        print()

    print("=== summary across all requested immediates ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

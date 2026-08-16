# M2.2 formatter 到 glyph pipeline

日期：2026-08-16（Asia/Taipei）

本切片只處理日版 B3EJ table B；不建立《孔明傳》資料，不建立翻譯 batch，也不把
ROM、完整日文、raw dump 或圖片寫入 Git。分析器是
`tools/analyze_m2_2.py`／`tools/m2_2_static.py`，所有 source record 只由既有
bounded extractor 寫入 ignored `research/sangokushi-eiketsuden-decoded.jsonl`。

## 結論分層

| 層級 | 結論 |
|---|---|
| confirmed-static | `0x0800D3FC` 的 formatter 會在 `sp+0x18` 建立 NUL-terminated output buffer；尾端呼叫 `0x0806ED80` veneer，該 veneer 是 `bx r2`，wrapper literal `0x0800D904` 指向 Thumb writer `0x0800CAD8`。 |
| confirmed-static | writer 的 SJIS double-byte path `0x0800CB62` → renderer `0x08008D18` → lookup `0x080650A4` → glyph expand `0x080650DC` → cache `0x02000000`，再由 `0x080656D4` copy 到 VRAM 並由 `0x08008914` 寫 tilemap。 |
| confirmed-static | codepage table 位於 file `0x024110C`／GBA `0x0824110C`，last-index literal `0x729`，因此 inclusive count 為 1834。lookup 命中後把 table index 傳入 glyph expander；source formula 是 `base + codepage_table_index * 0x20`，不是 `base + raw_sjis * 0x20`。 |
| confirmed-static | B[0] 三個 strict Shift-JIS sentinel 已分別得到 codepage index、兩組 static glyph chunk 位址／hash：U+90E8（部）、U+306B（に）、U+529B（力）。Unicode identity 與 glyph addressing 分欄保存。 |
| confirmed-static | table B 44/44 record decode→Shift-JIS encode 為 byte-identical、hash-identical、control-invariant；aggregate record hash 為 `e08935e581f822010e5f9f7ba14db556abfd80c25162048019d88f60d2b29af5`。這是 record-level no-op，不是 ROM 回插證明。 |
| provisional | table B 的 semantic label 仍沿用 M2 的 menu／battle-effect candidate；三個 sentinel 是結構與 codepage 交叉樣本，不把孤立 OCR 或 static glyph chunk 當成已知畫面位置。 |
| negative | M2.2 這次 bounded runtime attempt 沒有產生可用 pipeline report；沒有自然 consumer、formatter、writer、codepage、glyph、VRAM copy 或 tilemap breakpoint hit。 |
| pending | event index `<44`、自然畫面 reachability、controlled call 的 runtime output、cache／VRAM tile identity、可回插的 relocation／字庫覆蓋邊界。 |

## Static function boundaries

所有下列 span 都以 ARM7TDMI Thumb mode 逐 instruction 解碼；output writer、codepage
lookup、glyph expand 的 control-flow 分析排除了其後的 inline literal/data pool。分析器
對關鍵 callsite、literal slot、下一個 prologue 和分支 target 做 contract check。

| routine | file span | GBA span | instruction count | evidence |
|---|---:|---:|---:|---|
| formatter | `0x00D3FC–0x00D6B6` | `0x0800D3FC–0x0800D6B6` | 340 | `sub sp,#0xC8`；`add r5,sp,#0x18`；`strb 0,[r5]`；`bl 0x0806ED80` |
| wrapper | `0x00D8F0–0x00D904` | `0x0800D8F0–0x0800D904` | 9 | literal `0x0800D904 = 0x0800CAD9`；`bl 0x0800D3FC` |
| veneer | `0x006ED80–0x006ED82` | `0x0806ED80–0x0806ED82` | 1 | `bx r2`；不把 veneer 本身誤命名為 writer |
| output writer | `0x00CAD8–0x00CE06` | `0x0800CAD8–0x0800CE06` | 204 reachable | next prologue `0x0800CE1C`；literal pool `0x00CE06–0x00CE1C` 排除 |
| SJIS renderer | `0x008D18–0x008D6C` | `0x08008D18–0x08008D6C` | 38 | `bl 0x08065058`、`bl 0x080650A4`、`bl 0x080656D4`、`bl 0x08008914` |
| codepage lookup | `0x0650A4–0x0650DC` | `0x080650A4–0x080650DC` | 23 reachable | table base／last index literal；命中後 `bl 0x080650DC` |
| glyph expand | `0x0650DC–0x065254` | `0x080650DC–0x08065254` | 188 reachable | source base literals；index stack save `0x0650EC`；index×`0x20` `0x065108` |
| VRAM setup | `0x065058–0x065096` | `0x08065058–0x08065096` | 28 reachable | destination／length globals；call `0x0800022C` |
| VRAM copy | `0x0656D4–0x0656EA` | `0x080656D4–0x080656EA` | 10 | source `0x02000000`；call `0x08000214` |
| copy helper | `0x000214–0x00022A` | `0x08000214–0x0800022A` | 11 | 0x20-byte unit copy loop |
| tilemap writer | `0x008914–0x00896C` | `0x08008914–0x0800896C` | 44 | four halfword writes via literal base `0x02013050` |

### Byte-to-writer chain

Formatter input `r0` is the table-B record pointer. It consumes source bytes, builds the
stack buffer, writes a trailing zero, and passes the buffer pointer through `r0` at
`0x0800D6A0`. The call at `0x0800D6A2` targets the two-byte veneer, while the veneer uses
`r2` to dispatch to the output writer selected by the wrapper literal. This distinguishes
the indirect call mechanism from the actual writer boundary.

Within `0x0800CAD8`, the standard double-byte branch has lead-byte checks at
`0x0800CB0C`／`0x0800CB18`, builds the 16-bit code unit at `0x0800CB24`／`0x0800CB28`,
and calls `0x08008D18` at `0x0800CB62`. The renderer sets the destination through
`0x08065058`, asks `0x080650A4` to map the code unit, copies the expanded glyph through
`0x080656D4`, then writes four tilemap halfwords through `0x08008914`.

The writer's other direct output branches are recorded but not conflated with the
standard SJIS path: special-format handling at `0x0800CB3C` calls `0x0800C784`, the
ASCII path at `0x0800CBAA` calls `0x08018164`, the mapped single-byte path at
`0x0800CC1A` calls `0x08008E50`, and cleanup/return at `0x0800CDF8` calls
`0x08018E20`. M2.2 follows the double-byte path because the selected sentinels are
strict SJIS pairs; it does not infer glyph semantics for those other branches.

The static path therefore proves a writer and its data destinations. It does not claim
that the game reached this path in a natural menu or battle scene during this slice.

## Glyph addressing and Unicode identity

The codepage lookup scans 16-bit values at `0x0824110C` through inclusive index `0x729`.
On a match it returns the table index in the register later saved by glyph expand at
`0x080650EC`; glyph expand multiplies that index by `0x20` at `0x08065108` and selects
one of the two literal source bases. It writes 128 bytes to cache base `0x02000000`.
The renderer's setup computes VRAM destination as
`0x06000000 + (r1 << 5) + (3 << 14)` and supplies copy length `r2 << 5 = 0x80` for
this SJIS path. This is addressing evidence, not a claim about a particular runtime
tile's visual identity.

The three source-safe sentinel records are summarized below. The byte offset is within
the selected B[0] payload; no source text or raw glyph bytes are stored here.

| Unicode identity | SJIS code | B[0] byte offset | codepage index | source chunk offsets (two bases) | source chunk SHA-256 (two bases) |
|---|---:|---:|---:|---|---|
| U+90E8 部 | `0x9594` | 2 | 1301 | `0x23CE6C`, `0x22E92C` | `06656a5635bd1b9f4f7c8a00bc852b916a8d16d1546956d859d176ef052a6046`, `ca10afc0ec5f4d93ab0c1127cf32cff1beaf97e4701be7f2e53a0a696a7aa10d` |
| U+306B に | `0x82C9` | 6 | 103 | `0x2338AC`, `0x22536C` | `549dbf158c7108ae56223dc71b0b1243073a07324789459fd50a946326ef2f27`, `fdfe84398c36eefcb45817a9c6cca6cd5517c245aa794084f6f251bd78e10dfd` |
| U+529B 力 | `0x97CD` | 10 | 1501 | `0x23E76C`, `0x23022C` | `90e801079a5361ee9d698463fcff3e36ba06073f006e3c0628812479db587dcb`, `526e169e651b87f8a935c55a2638f16712d8f6c6eabf305c2e0f12f41f101bd7` |

The Unicode column comes only from strict Shift-JIS decoding of the selected source byte
sequence. The codepage index and static chunk hashes are independent addressing evidence;
runtime glyph identity remains pending until a breakpoint/watchpoint or controlled call
records the cache/VRAM data path.

## Event index boundary

The already-confirmed consumer at `0x08026054` remains bounded locally as follows:

```text
index = u16(r6+0x06) * u16(r6+0x08)
      + u16(r6+0x00) + u16(r6+0x04)
compare index against u16(r6+0x02)
r7 = u32(r6+0x1C) + index
event_byte = [r7]
table_index = event_byte & 0x7f
```

The branch at `0x080262EA` proves only `index < u16(r6+0x02)` before the record-byte
load. The later `& 0x7f` proves a numeric range of 0–127, not a safe table-B range of
0–43. No static relation from the r6 upstream caller/data structure to 44 was established
in this bounded slice. The harness now records, at `0x08026054`／`0x080262F8`, the r6
base, caller LR, fields at `+0x00/+0x02/+0x04/+0x06/+0x08/+0x1C/+0x24`, event-byte
pointer/value, event-array index and masked table index; every runtime record is labelled
`runtime-observed-only; not-static-proof`.

## Runtime result

`tools/trace_m2_runtime.py --pipeline --controlled-record` now installs breakpoints at
the consumer/index setup, wrapper, formatter, output writer, SJIS renderer, codepage
lookup, glyph expand, VRAM copy and tilemap writer, plus the shared KEYINPUT watchpoint.
Natural and controlled events are separate. A controlled B[0] pointer write to the
wrapper is labelled `controlled-consumer-call-hijack` and cannot establish natural
reachability.

One fresh, bounded attempt used this session's own mGBA process and port, without a bind
shim or interaction with another session. The process did not yield a usable harness
report or any accepted breakpoint event, so natural reachability, controlled output,
runtime index values and runtime glyph/cache/VRAM identity remain **pending**. This is a
runtime tooling result, not evidence against the static chain; the slice stops here rather
than repeating the listener experiment.

## Reproducibility and remaining boundary

Source-safe static reports can be regenerated to ignored temporary files:

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m2_2.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-m22-static.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_table_b_roundtrip.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-table-b-roundtrip.json
```

The first-translatable-batch gate is still closed. Before creating any translation ledger,
we need a proven event index `<44` path or a separately bounded record-selection contract,
one natural or explicitly controlled runtime output observation, glyph/cache/VRAM evidence
that agrees with the static addressing, and a full encoder/insertion boundary beyond the
record-level no-op check.

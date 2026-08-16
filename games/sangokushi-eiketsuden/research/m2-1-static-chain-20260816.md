# M2.1 table B static consumer chain

日期：2026-08-16（Asia/Taipei）

本切片承接 M2 的 B3EJ candidate B[0]，改以可重現的 ARM7TDMI Thumb static
consumer chain 前進；不把 static chain 當成 runtime glyph proof，也不建立翻譯或
回插批次。完整原文只由 extractor 寫入 ignored local source table，tracked 文件
只保存 offset、count、hash、反組譯摘要和控制碼統計。

## Table B boundary

`tools/analyze_table_b_chain.py` 對本機 ROM 做 bounded read-only analysis，結果如下：

| 證據 | 結果 | 狀態 |
|---|---|---|
| table base | file `0x0D1FFC` / GBA `0x080D1FFC` | confirmed-static |
| contiguous pointer run | 44 words，結束於 file `0x0D20AC`（exclusive） | confirmed-static |
| terminator／adjacent structure | `0x0D20AC` 的 word 為 `0x00000000`；直到下一個 table C base `0x0D20D8` 的 gap words 都不是 ROM pointer | confirmed-static |
| record target starts | 26 unique targets，file `0x078528–0x0786FC` | confirmed-static |
| final record boundary | 最大 record 的 NUL 終止後為 file `0x07870B` | confirmed-static |
| payload lengths | 14 bytes × 16、16 bytes × 22、18 bytes × 6 | confirmed-static |
| terminator／codepage | 44/44 有 `0x00` terminator；44/44 可由標準 Shift-JIS 解碼 | confirmed-static |
| line feed | 0 個 record 含 `0x0A` | confirmed-static |
| reviewed formats | `%s`、`%d`、`%u`、`%%` 都是 0 | confirmed-static for table B only |
| opaque controls | 未發現 `<0x20` 且非 tab/LF 的 byte；extractor 仍保留 opaque 統計欄位 | confirmed-static for table B only |

這將 table B 的靜態 entry count 從候選值提升為 44；不把相鄰的 11 個非 pointer
words 或 table C 的 4-entry pointer pool 合併進來。

## Valid Thumb function and chain

### Function boundary and literal search

選定的有效 Thumb function 是 file `0x026054`（GBA `0x08026054`）。其 dispatch
prefix、table-B case block、epilogue 都能以 Capstone ARM/Thumb mode 逐 instruction
解碼：

| span | 證據 |
|---|---|
| `0x026054–0x026080` | `push {r4, r5, r6, r7, lr}` 開始；dispatch bound 為 `cmp r4, #0x22` |
| jump table `0x026088` | 35 entries；`0..0x22` 的所有 target 都落在 `0x08026054–0x080264A4` |
| `0x02629C–0x02634C` | table B consumer case，78 個 Thumb instructions 全部解碼 |
| `0x026494–0x0264A4` | `movs r0,#0` 到 `bx r1` 的 epilogue |
| next prologue | `0x080264A4` 是下一個 `push {r4, r5, r6, r7, lr}` |

整個 ROM 的 aligned word search 只找到一個指向 table B range 的 literal：file
`0x026350` 的 value 是 `0x080D1FFC`。該 literal 在有效 case block 中由
`0x080262F8: ldr r2, [pc, #0x54]` 取出；其 PC-relative target 正好是
`0x08026350`。同一 literal 沒有 ARM PC-relative LDR candidate，故本鏈以有效
Thumb caller 為準，而不是把資料區誤當 ARM code。

### Pointer／record／reader chain

在 `0x080262EC–0x08026308` 可重現下列順序：

```text
event index 已由 r6 欄位計算並與 r6 欄位上限比較
    -> r7 = [r6, #0x1C] + index
    -> ldrb r0, [r7]
    -> r0 &= 0x7F       (清除 high flag bit)
    -> r0 <<= 2
    -> r0 += 0x080D1FFC
    -> ldr r0, [r0]     (table B record pointer)
    -> BL 0x0800D8F0    (byte-reader wrapper)
```

`0x0800D8F0` 的有效 Thumb span 是 `0x0800D8F0–0x0800D904`，其下一個 branch
target 是 `0x0800D3FC`。`0x0800D3FC–0x0800D6B6` 也是完整可解碼的 Thumb function，
可觀察到：

- `ldrb r2, [r0]` 從傳入 record pointer 讀 source byte；
- `cmp` 讀值與 `0`，形成 NUL 終止路徑；
- `cmp` 讀值與 `0x25`，形成 `%` 格式解析路徑；
- function 尾端回到 `0x0806ED80` 的 output-building call，再以 `bx` 返回。

因此目前已 confirmed 的 static chain 是：

```text
valid Thumb consumer
  → table-B base literal
  → masked event-byte index / word load
  → NUL-terminated Shift-JIS record pointer
  → byte reader / format parser
```

這裡的最末端只確認 byte reader／format parser；沒有把 `0x0806ED80` 或任何後續
routine 猜成 glyph writer，也沒有確認 glyph address、tile index 或 Unicode glyph
identity。

### Caller index bound

這條 consumer 在 table load 前只形成 `event_byte & 0x7F`，所以可由本身反組譯
證實的最大 index 是 127，而不是 43。`cmp r4,#0x22` 是上層 dispatch table 的
35-entry bound，不是 table B byte index bound。因而：

- table B 的 ROM 結構邊界與 entry count 44：`confirmed-static`；
- consumer 的「永不讀取 entry 44–127」：`not-proven`；
- 若要把 caller bound 升為 confirmed，下一切片必須從 `r6` 的上游 caller／資料
  結構證明 event byte 的有效值域，或由 runtime breakpoint 觀察實際 index。

## Extractor and local source table

新增的 bounded tools：

- `tools/table_b_common.py`：table boundary、ARM/Thumb literal／branch 檢查、record
  結構與控制碼統計共用函式；不把 source text 放進 static report。
- `tools/analyze_table_b_chain.py`：輸出 counts、offsets、hash、function spans、
  branch target、index-bound 狀態和 chain scope。
- `tools/extract_table_b.py`：只將 44 筆 record 寫入 ignored
  `research/sangokushi-eiketsuden-decoded.jsonl`；每筆包含 `string_id`、`locale`、
  `text` 和 source provenance，沒有提交到 Git。

本機 extractor 結果：44 lines、26 unique source hashes、44/44 Shift-JIS valid；
`git check-ignore` 確認 `**/research/*-decoded.jsonl` 規則生效。tracked 報告不保存
完整日文，也不產生 translation ledger。

ROM-independent tests 覆蓋：

- Thumb literal target 與完整 instruction-span 解碼；
- 44-pointer boundary、zero terminator、相鄰 structure gap；
- Shift-JIS／NUL／LF／格式參數統計；
- unknown control byte 的 opaque 保留；
- extractor JSONL 欄位與不輸出 raw bytes。

## Runtime pending（最多兩次、無 shim）

static chain 找到可用的 wrapper breakpoint 後，既有
`tools/trace_m2_runtime.py` 已加入 optional `0x0800D8F0` breakpoint。依本切片界線
做了兩次全新 headless process，均未使用 bind shim：

1. 第一次可啟動並連到 GDB，但 harness 在第一次 runtime memory response 解析時
   遇到 transient non-hex response；child 已清理，沒有 pointer／wrapper hit。
2. 第二次 GDB transport 穩定：`qSupported`、`?`、I/O／VRAM read 均成功，
   `KEYINPUT` read watchpoint 在 PC `0x0805CF5E` 命中 16 次；有限輸入後沒有
   table pointer、record 或 `0x0800D8F0` wrapper hit。

因此 runtime edge 維持 `pending`，但不再阻擋 M2.1 的 static progress；本切片沒有
聲稱實際 menu／戰役畫面已到達，也沒有聲稱 glyph writer 已定位。

## 狀態分層與下一步

- **confirmed**：table B 44-entry boundary、Shift-JIS/NUL 結構、有效 Thumb function
  boundary、table base literal、masked index／record load、record pointer 到 byte
  formatter 的 static call chain。
- **provisional**：table B 的 menu／battle semantic classification；event byte 的
  high bit 是 flag 的解讀（清 mask 的行為已確認，flag 語意未確認）。
- **negative／pending**：caller index `<44`、formatter 到 glyph/tile writer、font
  addressing、runtime pointer／wrapper breakpoint hit、Unicode glyph identity。

下一個安全 static edge 是從 `0x0800D3FC` 的 output-building call
`0x0806ED80` 往下確認 byte-to-glyph／tile writer；在此之前不開始翻譯或回插。

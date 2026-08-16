# M2 固定字型／codepoint pipeline 邊界（2026-08-16）

## 範圍

本回合只重跑已審核的固定 code path，沒有新增文字窗、pointer scan、runtime
transport，也沒有讀出或提交原文／glyph／RAM／VRAM bytes。可重跑工具是
[`tools/font_pipeline_probe.py`](../tools/font_pipeline_probe.py)，metadata receipt
是 [`m2-font-pipeline-metadata.json`](m2-font-pipeline-metadata.json)。工具只輸出
ROM identity、固定位址、direct-call count、bounded span hash、lookup table 的
hash／計數與分類。

## Confirmed static

### asset stride、分派與 transform

- `0x080014F4` 的固定格式迴圈只有 6 個已解出的 direct callsite；其中兩個
  `0x08001556`、`0x080015F8` 把計算出的 codepoint index 送到
  `0x08001414`。
- `0x08001414` 的 `lsls r2,#5` 與 literal `0x080DDCC4` 固定形成
  `0x080DDCC4 + codepoint_index*0x20`。這是 32-byte asset slot 的靜態地址算術，
  不是任何五窗 `string_id` 的容量或指標證明。
- 同一 routine 的 parity mask 只把輸出分到 `0x080011A8` 或 `0x080012E0`；兩者
  各只有一個 direct caller（`0x08001454`、`0x08001440`）。兩個 bounded span
  都含固定 `& 0x03 → 0x03001464 → ldrb` lookup expansion pattern，並使用
  `0x03000560` scratch literal。
- 因此可以把「2-bit lookup expansion 的 static shape」列為 confirmed-static；
  不能把 `0x080DDCC4` 任一 slot 直接稱為某個日文 glyph，也不能把 scratch
  視為已確認的 VRAM source。

### codepoint lookup pool

`0x08004D90` 的 direct callsite 仍精確只有 `0x080015C4`、`0x08004D60`。五個
已固定的 ROM pointer slots 與 bounded `0x100`-byte halfword windows 都通過
identity／address／hash 驗證：

| slot | table | nonzero bytes | unique halfwords |
| --- | --- | ---: | ---: |
| `0x00741D80` | `0x080FFE80` | 254 | 125 |
| `0x00741D84` | `0x080FFF40` | 250 | 120 |
| `0x00741D88` | `0x080FFFBC` | 246 | 124 |
| `0x00741D8C` | `0x080FFFF4` | 229 | 114 |
| `0x00741D90` | `0x08100070` | 152 | 84 |

這支持「固定 codepoint lookup pool」的 static contract；表格重疊且不是五張
獨立完整 codepage，仍不得據此宣稱完整日文碼頁或寬度語義。

## Provisional、negative 與 unknown

| 邊界 | 狀態 | 限定 |
| --- | --- | --- |
| `0x080DDCC4 + index*0x20` asset address math | **confirmed-static** | 只確認固定算術與 slot stride |
| transform 的 `&0x03` lookup expansion shape | **confirmed-static** | 只確認固定 routine bytes 與 IWRAM table literal |
| `0x08004D90` entry／五個 lookup slots | **confirmed-static** | 不是完整 codepage 證明 |
| asset 的實際 glyph semantic／bpp identity | **provisional-static** | 需要 runtime source／glyph cross-check |
| complete Japanese codepage、字寬與 width semantics | **unconfirmed** | 不能開始翻譯或回插 |
| strict record→parser→font asset live edge | **unconfirmed** | M1.8 clean trace source read 仍為 0 |
| scratch→VRAM writer | **unconfirmed** | `0x08001DBC` 目前只確認 IWRAM tilemap writer |
| capacity、pointer rewrite、round-trip、BPS | **unconfirmed** | 沒有 builder 或 ROM write |

本回合對已分配 port `24387` 做了唯讀 GDB 基線連線嘗試；sandbox 先回報
`PermissionError: Operation not permitted`，受限升權重試又因 approval stream
disconnect 被拒。這是本 session 的 environment-negative，不是遊戲執行結果，且
沒有接觸或停止任何 mGBA process。runtime source／glyph 證據仍須在可用的本作
獨立 mGBA session 重新取得。

## 下一個最小切片

保留上述 static contract，待 runtime 能力可用時只在同一 session 追蹤
`0x080014F4`／`0x08001414`、`0x03000560` 與一個實際 writer，並要求 source
pointer、caller、codepoint lookup 與 glyph destination 同時有 receipt。不得把
這個 static pipeline 直接用作翻譯、容量推論或回插入口。

# M2 parser→format→RAM render chain（2026-08-16）

## 範圍

本回合只追蹤固定 `BL 0x080025CC` direct callsite 與其立即的 bounded
consumer；沒有再做文字窗 pointer scan、沒有寫入 ROM／RAM，也沒有使用畫面 OCR
當作 source。可重跑工具是
[`tools/renderer_chain_probe.py`](../tools/renderer_chain_probe.py)，receipt 是
[`research/m2-renderer-chain-metadata.json`](m2-renderer-chain-metadata.json)。
輸出只有 identity、位址、literal、hash 與 count。

## Confirmed static：parser 的四個 direct callsite

以 Thumb-2 `BL` 目標精確解碼後，整個 ROM 只找到 4 個直接呼叫
`0x080025CC` 的位置：

| file offset | GBA PC | parser 後的固定邊 |
| --- | --- | --- |
| `0x00164C` | `0x0800164C` | `0x080014F4`，共用 formatted buffer `0x03001468` |
| `0x001D92` | `0x08001D92` | `0x08001A10`，共用 formatted buffer `0x03001468` |
| `0x001E26` | `0x08001E26` | `0x08001DBC`，使用 caller stack 的 bounded 0x20-byte buffer |
| `0x00281C` | `0x0800281C` | wrapper return |

因此 `0x08001E26 → parser → stack buffer → 0x08001DBC` 是一條已由固定 direct
call／register setup 證明的 static edge；仍不是某個五窗 `string_id` 的 live edge。

## Confirmed static：格式與中間 RAM writer

`0x080014F4` 逐 byte 處理 parser output：

- NUL 結束；LF `0x0A` 進入換行／游標處理；
- `0x80–0x9F`、`0xA1–0xDF` 走單位元組分支；
- 其他 byte pair 依 lead `<=0x87` 或 `>0x87` 做固定減法，再用
  `(lead-adjusted)*3*0x40 + trail - 0x40` 形成 index，交給
  `0x08001414`；
- `0x08001414` 以 `0x080DDCC4 + index*0x20` 形成 ROM asset address，並呼叫
  `0x080011A8`／`0x080012E0` 將候選資料轉到 IWRAM scratch `0x03000560`。
  `0x03001464` 是相鄰的 lookup-table literal，故目前只能稱為
  `static-glyph-source-candidate` 與 `static-packed-glyph-to-IWRAM-candidate`。

`0x08001DBC` 並不直接寫 VRAM。它以 literal `0x03000060` 為 base，使用
  `0x03000060 + y*0x40 + x*2` 寫 halfword tilemap／render buffer，另有
  `0x03001461` flag 與 `0xFFFFE000` tile attribute。後續 IWRAM→VRAM 搬運尚未
  由本回合證明，這個修正刻意避免把中間 RAM writer 誤升格成 glyph VRAM writer。

## Provisional／negative／unknown

| 邊界 | 狀態 | 限定 |
| --- | --- | --- |
| parser→formatted buffer | **confirmed-static** | 只證明固定 direct call／buffer 形狀 |
| parser→RAM tilemap writer | **confirmed-static** | `0x08001E26→0x08001DBC`，不是 live record |
| Shift-JIS-like arithmetic | **confirmed-static** | 與 strict extractor 相容，但尚未拿到 runtime source read |
| `0x080DDCC4` asset | **provisional-static** | 32-byte stride 的 glyph source candidate，不是 glyph identity |
| `0x03000560` transform | **provisional-static** | packed-glyph→IWRAM candidate，格式尚未確認 |
| IWRAM→VRAM writer | **unconfirmed** | 本回合只找到 IWRAM tilemap writer |
| 五窗 concrete `string_id`→parser | **unconfirmed** | M1.8 clean trace 仍是 source read 0 |
| codepage、glyph identity、capacity、round-trip、翻譯 | **unconfirmed** | 不可開始回插或填入譯文 |

下一個最小切片是使用獨立 mGBA session，在 `0x080025CC`、
`0x080014F4`、`0x08001E26`／`0x08001DBC` 中選單一入口／writer breakpoint，
取得一次 source pointer、formatted buffer、RAM tilemap destination 與 caller；
若 runtime 權限仍不可用，必須把結果記為 environment negative，不把 static chain
冒充成 runtime confirmation。

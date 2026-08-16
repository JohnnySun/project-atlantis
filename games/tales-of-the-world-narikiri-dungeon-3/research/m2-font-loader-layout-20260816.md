# M2 font-loader output geometry（2026-08-16）

## bounded static proof

`tools/font_loader_layout_probe.py` 對 `0x080021A8–0x08002310` 做固定範圍驗證，
沒有做新 pointer scan，也不讀 source、RAM 或 VRAM。全 ROM direct-call set 仍是
唯一的 file callsite `0x015C26`；entry 先把 caller `r0` 保存成 context `r4`，再
建立四個 output pointers：

| group | context offset | bytes |
| --- | ---: | ---: |
| 0 | `+0x00` | `0x20` |
| 1 | `+0x20` | `0x20` |
| 2 | `+0x40` | `0x20` |
| 3 | `+0x60` | `0x20` |

因此「單一 `0x20`-byte asset slot → bounded `0x80`-byte caller-context expansion」
是 **confirmed-static byte geometry**。程式對 asset 的 `+0x00` 與 `+0x10` 兩個
half 各做受限的 8 次 halfword/lookup/word-store loop；lookup literal 是
`0x03001464`，asset literal 是 `0x080DDCC4`，且 `0x08002100` init callset
仍為四處固定 caller。這些是輸入／輸出大小與 lookup 形狀，不是 glyph 語意。

## 嚴格邊界

這個 receipt 不能單獨證明：

- 任何五窗 strict record 實際流入 `r1`；
- `0x080DDCC4` 的資料是日文 glyph、其 bpp／字寬或完整 codepage identity；
- context expansion 後的 RAM decoder、IWRAM tilemap 或 VRAM writer；
- event、角色／服裝／技能、戰鬥與選單 record 類別；
- 容量、指標更新、壓縮界線、round-trip、BPS 或翻譯。

2026-08-16 的同一個 runtime probe 仍因獨立 port setup negative 而沒有 live stop；
這份 static geometry 不會取代 `m2-font-record-runtime-20260816.md` 所要求的
source read／asset read runtime evidence。


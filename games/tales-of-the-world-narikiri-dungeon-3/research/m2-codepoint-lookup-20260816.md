# M2 codepoint lookup pointer pool（2026-08-16）

## 固定範圍

`0x080014F4` 的格式 loop 在 bounded non-direct-byte 路徑呼叫
`0x08004D90`（file `0x15C4`）；全 ROM 對該固定目標只找到兩個 direct callsite：
`0x080015C4` 與 `0x08004D60`。本回合沒有掃描其他 pointer 或推測資料窗。

`0x08004D90` 使用五個已確認的 literal-pool slots：

| literal file offset | loaded ROM table address |
| --- | --- |
| `0x741D80` | `0x080FFE80` |
| `0x741D84` | `0x080FFF40` |
| `0x741D88` | `0x080FFFBC` |
| `0x741D8C` | `0x080FFFF4` |
| `0x741D90` | `0x08100070` |

[`tools/codepoint_lookup_probe.py`](../tools/codepoint_lookup_probe.py) 只驗證這五個
slot 與每個 target 的 bounded 0x100-byte halfword window，receipt
[`research/m2-codepoint-lookup-metadata.json`](m2-codepoint-lookup-metadata.json)
只保留 hash、non-zero、unique 與 signed range。因為五個 bounded windows 互有
重疊，不能把它們未經進一步邊界分析當作五張獨立完整表。

## Confirmed／provisional 分層

- **confirmed-static：** `0x08004D90` 的 direct callsite、五個 pointer slot 與
  ROM halfword table window 都可由 B3TJ 固定 bytes 重現。
- **provisional-static：** 這些 table 被格式 loop 用作 character/codepoint lookup，
  並可能承擔 ASCII、halfwidth 或特殊 byte 的轉換；目前只稱
  `static_codepoint_lookup`，不稱完整日文 codepage。
- **unconfirmed：** 五窗 strict record 或 control-only template 的 runtime source
  read、table entry 的 glyph identity、字寬語義、IWRAM→VRAM 搬運、capacity、
  round-trip 與翻譯。

這份證據把「byte→halfword lookup」與先前的 `0x080DDCC4 + index*0x20` asset
candidate 分開；兩者仍須同一個 live source record 的寄存器／caller／RAM receipt
才能合併成可回插的 codepage/font contract。

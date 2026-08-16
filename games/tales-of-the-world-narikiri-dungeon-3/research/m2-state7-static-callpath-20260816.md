# M2 state 7 static text-candidate callpaths（2026-08-16）

## 範圍

這是一個固定 direct-BL call-edge receipt，不是新的 pointer scan，也不是 runtime
文字證明。`tools/state7_static_callpath.py` 只驗證先前反組譯時已選定的兩條短 chain：

```text
state7 0x080A85D8
  -> ... -> 0x080014F4 formatter
state7 0x080A85D8
  -> ... -> 0x08001D88 -> 0x080025CC parser
```

每一條 edge 的 4-byte BL instruction 只以 aggregate SHA-256 留 receipt；工具不輸出
source bytes、完整 code、RAM、VRAM 或影像。這兩條 chain 只提供下一次 GDB session
的窄 breakpoint/caller 選擇，不改變 natural-flow 與 argument-injected 的證據分級。

## Confirmed static

| chain | edges | terminal |
| --- | ---: | --- |
| state7 → formatter | 6 | `0x080014F4` |
| state7 → parser | 5 | `0x080025CC` |

`state7 → parser` 的最後一段是固定 `0x08001D88 → 0x080025CC`，其 BL callsite 為
`0x08001D92`；formatter chain 的最後一段是 `0x08001640 → 0x080014F4`，callsite
為 `0x08001652`。所有 edge 與 B3TJ identity 由 verifier 重新檢查。

## Evidence boundary

- **confirmed-static：** state 7 code region 含這兩條直接可解析的 call chain。
- **provisional runtime candidate：** `0x08001D92`、`0x08001652` 是下一次同一 GDB
  connection 可設的窄 caller/consumer breakpoint。
- **unconfirmed：** state 7 自然流程是否在可用 menu/event 中走到 chain、parser 的
  `r1` 是否落入五窗 strict record、source read、RAM decoder、glyph identity 與
  VRAM writer。
- **negative：** 尚未把 listener setup failure 當作遊戲 negative；目前沒有新的
  runtime session receipt。

## Reproducible command

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/state7_static_callpath.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --out /private/tmp/tow-nd3-state7-static-callpath.json
```

`tools/state7_readiness_probe.py` 現在可在同一個 bounded connection 對這兩個
callsite 做一次性 breakpoint，再讓 `0x080025CC` entry 接續捕捉。下一個 runtime
最小切片仍是：以正常 state 7 導覽，於固定 callsite 取得第一筆 strict source pointer，
再從 source read 追到 RAM output；不能把本 receipt 當作 M2 live renderer 或翻譯開始
條件。

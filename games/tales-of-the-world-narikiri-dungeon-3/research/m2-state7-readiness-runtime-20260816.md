# M2 state 7／A82AC readiness bounded runtime（2026-08-16）

## 範圍與方法

本回合只追蹤正常 M1.8 `state 4 → 7` return 後的固定 loader/readiness path，沒有
擴大 resolver 或 pointer scan，也沒有覆寫 state、resource object、save 或 ROM。
使用全新的本作 mGBA standard SDL/GDB process、單一 `127.0.0.1:2345` listener
與單一 GDB connection；ROM identity 在 invocation 內確認為
`TOWNARIKIRI3`／`B3TJ`／`AF`／16 MiB／CRC32 `1867CCEF`。

正常 state 4 input 部分沿用已審核的 [`m18_a1ac_probe.py`](../tools/m18_a1ac_probe.py)：
只在 KEYINPUT read stop 對 `r1` 寫入 active-low START/A，檢查 GDB `OK`，並取得
`A1AC → edge bit 0 → object +0x54 → A2C0 success → 0x08005E12`。state return
receipt 的 current/next/previous 是 `04`／`07`／`FF`，固定畫面只保留 hash metadata。

return 後由 [`state7_readiness_probe.py`](../tools/state7_readiness_probe.py) 在同一
連線執行 parser trace。post phase 的固定觀察點是：

- state7 handler entry `0x080A85D8`，一個 one-shot breakpoint；
- readiness check entry `0x080A82AC`，一個 one-shot breakpoint；
- reviewed parser `0x080025CC`、IWRAM writer candidate `0x08001DBC`；
- KEYINPUT read watch，以及 parser 只有在 exact strict record start 才會掛上的
  source read-watch。

A82AC 只額外讀一個 guard 通過的 `r0 + 0x28` byte，輸出 pointer、address、數值與
status metadata；不輸出該物件或其他 RAM bytes。post sequence 是 `none:256`，
`post_max_events=256`、`post_max_stops=300`、`post_max_hits=8`。

## confirmed-runtime

### 正常 state return

- `0x0800A1AC`、edge bit 0、A2C0 entry／caller-after success 與
  `0x08005E12` 均命中；三次必要的 KEYINPUT register write 都取得 `OK`。
- state return stop 的 PC 是 `0x08005E12`，state metadata 為 current `4`、next
  `7`、previous `-1`；state return 的固定 VRAM/palette/OAM hash 與既有 M1.8
  receipt 一致。

### state7 → A82AC

| stop | PC | LR | 重要寄存器／欄位 |
| --- | --- | --- | --- |
| state7 entry | `0x080A85D8` | `0x08005EED` | `r1=0x02000001`、`r2=0x08741D94` |
| A82AC entry | `0x080A82AC` | `0x080A8509` | `r0=r5=0x0200D10C`、`r1/r6=0x0E`、`r2=0x0300003C` |
| readiness field | `0x0200D134` | — | `r0 + 0x28`，value `0` |

`0x0200D10C` 落在受限 RAM range；`0x0200D134` 是由該 `r0` 推導出的單位元組
欄位，讀取 status 是 `metadata-byte-read`。這確認本次正常 state7 執行確實
進入 A82AC 及其 resource/readiness object candidate；它不是文字 source pointer。

## negative／unknown

- post phase 消費 256 個 bounded KEYINPUT events 後結束：
  `sequence-exhausted-without-parser-strict-record-hit`。
- `parser_hits=0`、`source_read_hits=0`、`output_write_hits=0`、`writer_hits=0`；
  因此本次沒有取得五窗 strict record、source reader、RAM decoder、glyph lookup
  或 VRAM writer 因果鏈。
- state7 與 A82AC 的命中是 **natural-flow** 證據；沒有 argument-injected
  record，也沒有用 state/object override 讓它命中。A82AC `r0+0x28=0` 只表示本次
  readiness snapshot，不能單獨推出所有 state7 分支都不可達。
- `state7` handler entry 後在本 bounded window 沒有進一步文字 parser 證據；這是
  loader/readiness boundary negative，不是「遊戲沒有文字」或「五個資料窗錯誤」的
  證明。`state3`、其他 menu/event caller 仍未確認。
- codepage、glyph identity、控制碼 semantics、字寬、容量、回插與翻譯仍未完成；
  本回合不改變 ledger 中 8,938 筆皆為 `untranslated` 的狀態。

## 可重跑命令

先以本機自有 process 啟動 B3TJ mGBA，確認 listener ownership，再執行：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/state7_readiness_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <independent-b3tj-gdb-port> \
  --post-sequence none:256 --post-max-events 256 --post-max-stops 300 \
  --post-max-hits 8 --post-per-event-timeout 5 \
  --output /private/tmp/tow-nd3-state7-readiness.json
```

輸出只含 identity、register／stop、state、pointer、單位元組欄位值、hash、count
與 termination metadata。`/private/tmp/tow-nd3-state7-readiness.json` 不是提交
來源；ROM、sav、raw dump、完整原文與圖片都維持 ignored／本機範圍。

下一個最小缺口仍是自然流程的第一個 strict text consumer：需要從可重現的
source read PC/LR 追到 decoder／output，並在有實際 glyph sink 時做 ROM→RAM→VRAM
交叉驗證；A82AC readiness edge 不足以開始翻譯或回插。

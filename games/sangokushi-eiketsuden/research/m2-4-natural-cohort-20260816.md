# M2.4 natural Table-B cohort and normal-path state gate

日期：2026-08-16（Asia/Taipei）。本切片只處理日版 B3EJ 的 Table B，不建立
《孔明傳》資料，不建立翻譯 batch，也不提交 ROM、完整日文、runtime dump、圖片或
mGBA build。runtime 報告只留在 `/private/tmp/`；本文件只保存按鍵序列、計數、位址、
狀態、寄存器 provenance 欄位與 hash。

## 結論摘要

| 分類 | 結論 |
|---|---|
| confirmed-static | initializer `0x080264A4` 將 consumer pointer `0x08026055`（Thumb）寫入 descriptor `r6+0x10`，將 builder count 寫入 `r6+0x02`，將 caller stack event buffer 寫入 `r6+0x1C`，並呼叫 normal state loop `0x0801A738`。 |
| confirmed-static | `0x0801A738` 先檢查 `u32(r4+0x14)` state/readiness field，再呼叫 `0x0801A12C`；非零 poll result 與 `r4` 一起送到 `0x0806ED80: bx r2`，其中 `r2=[r4+0x10]`，因此自然 consumer edge 是 descriptor function-pointer dispatch，不是 direct `BL 0x08026054`。 |
| confirmed-static | reviewed spans 的 Thumb function boundaries、branch targets 與 inline jump-table/data gaps 已由 `tools/m2_4_static.py` 驗證；dispatcher gap `0x01A51C–0x01A588` 沒有被當成程式反組譯。 |
| negative / bounded-natural | 兩條 fresh-process、single-connection、bounded KEYINPUT path 均只停在 title/input-read loop；各 32 個 watchpoint stops，builder／consumer／formatter／writer 全為 0，VRAM before/after hash 相同。自然 consumer cohort `0`，因此沒有自然 actual index 可宣稱 `<44`。 |
| provisional | `r4+0x14` 是 normal event loop 的 state/readiness gate；其確切遊戲模式語意尚未由 static data 命名。`0x0801A12C` 的返回集合 `0,4..17` 是 input selector-like 值，不可直接當成 Table-B event-byte/index bound。 |
| unknown | 第一條自然跨過 state gate 的 menu／battle 路徑、normal runtime table `0x02014E78` 的實際 sentinel/count、自然 event byte provenance、自然 B entry→formatter→glyph receipt。 |

## Natural path receipts

報告位於 ignored `/private/tmp/b3ej-m24-path1.json` 與
`/private/tmp/b3ej-m24-path2.json`；下表只保存可審核 metadata，不保存 report 原文或
memory dump。

| path | fresh process／port | key sequence | window | screen／VRAM metadata | builder hits | consumer hits | result |
|---|---|---|---|---|---:|---:|---|
| `title-to-main-menu` | headless mGBA／`39123` | `none:8,start:4,none:20` | 32 input events；約 45.083 s | `DISPCNT=0x0140`、`BG0CNT=0x1D00`、`BG1CNT=0x1E01`、`BG2CNT=0x1F02`；VRAM before/after SHA-256 `57ac3f390f4e9d4549ccb2a377688ae96f1890b16a4ee3c266816454dd1b753f` | 0 | 0 | 所有 stop 為 KEYINPUT read watchpoint，PC `0x0805CF5E`；`natural_reachability=not-observed`。 |
| `title-to-main-menu-start-hold` | native mGBA／`2346` | `none:4,start:8,none:20` | 32 input events；約 45.843 s | 相同 `DISPCNT/BG` metadata；VRAM before/after SHA-256 同為 `57ac3f390f4e9d4549ccb2a377688ae96f1890b16a4ee3c266816454dd1b753f` | 0 | 0 | 所有 stop 為 KEYINPUT read watchpoint，未進入 builder／consumer／pipeline。 |

這兩條是有效的 bounded natural negatives，不是「遊戲永遠不會到達 consumer」的全域否證。
本切片沒有把先前 listener/forward 失敗的嘗試算成自然 path，也沒有增加 controlled
fixture 的結論。

## Static caller/state chain

`tools/m2_4_static.py` 只對以下已審核 span 反組譯：initializer
`0x0264A4–0x026646`（排除三個 inline data gap）、descriptor wrapper
`0x01A4B8–0x01A4CC`、state loop `0x01A738–0x01A768`、event poll
`0x01A12C–0x01A1FC`、selector wrapper `0x01A720–0x01A738`，以及 dispatcher
`0x01A504–0x01A718`（排除 selector jump table）。可重跑命令：

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/m2_4_static.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-m24-static.json
```

確認的 chain：

```text
initializer r6+0x10 = 0x08026055 (Thumb consumer)
initializer r6+0x02 = u16(event-builder return)
initializer r6+0x1c = caller stack event buffer
initializer BL 0x0801a738
  -> if u32(r4+0x14) != 0, call 0x0801a12c
  -> if poll result != 0, r2 = [r4+0x10], r0 = r4, r1 = poll result
  -> 0x0806ed80: bx r2
  -> 0x08026054 Table-B consumer
```

initializer 在 `0x08026526` 先把 input structure `+0x02` 的 byte 經 `0x080241D0`
取出，與 `r1=0` 傳給 `0x08021A44`；該函式以 literal slot `0x08021A5C` 取得
EWRAM state table `0x0203544C`，實際 predicate 為
`nonzero([0x0203544C + u16(r1) + (u16(r0) << 3)])`，結果再寫入 `r6+0x14`。
這確認了 state gate 的資料來源，但尚未替該 EWRAM table 賦予 menu／battle 語意。

`0x0801A12C` 靜態返回值集合為 `0,4,5,6,7,8,9,10,11,12,13,14,15,16,17`；
這是 input/poll selector evidence，不是 event array byte 的 Unicode 或 Table-B
index identity。consumer 仍只保證 local `u16(r6+0x02)` 與 `event_byte & 0x7F`，
正常 builder count 仍來自 `[0x02014E78]` 的 `0xFF` terminated table；沒有靜態
證據把該 count 或 event byte 全域限制到 44。

## Runtime and translation boundary

自然 builder 沒有 hit，所以本切片沒有 runtime `0x02014E78` table sentinel receipt，
也沒有自然 B entry→formatter→cache／VRAM／tilemap receipt。M2.3 的 controlled
`B[0]` receipt 仍單獨標示為 controlled，不能移入本自然 cohort。

因此：

- natural index gate：`unknown`，不是 confirmed `<44`；
- normal-path count：`unknown`，不能以 empty path 的 44 外推；
- glyph addressing：沿用 M2.2 static／M2.3 controlled evidence；
- Unicode identity：`0x9594→U+90E8` 的 controlled identity 與三個 static sentinel 仍分欄；
- translation batch／ROM insertion：本切片不開始。

下一個安全 runtime 路徑應以 state field `r4+0x14` 的自然初始化／menu 或 battle
mode gate 為入口；若沒有新的可重現導航證據，應先從其上游 initializer/state owner
追蹤，而不是延長 title KEYINPUT loop 或擴大 controlled call。

## 後續 transport negative（同日 bounded retry）

在完成本批次 static／record gate 後，另以本 session 自行啟動的 headless mGBA
與 B3EJ ROM 做一次乾淨對照；程序在 Ctrl-C 前輸出 `Debugger: Couldn't open socket`
（該 build 僅嘗試預設 GDB port `2345`），沒有建立可用 listener 或 GDB connection。
只停止這次由本 session 啟動的程序；未連線、未讀寫 ROM／save，也沒有把它算成新的
natural path。這筆 negative 只表示該 headless build 的本次 transport readiness
失敗，不能否定既有 static chain、已完成的 E fixed-slot round-trip，或把自然 runtime
缺口宣稱為永久外部阻塞。

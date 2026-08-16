# A9PJ M39 mGBA runtime port boundary（2026-08-16）

M39 是一次有界的 runtime 替代路徑檢查，不是文字路徑 negative，也不新增候選／
decoder／ledger row。目標是確認現有本機 mGBA 是否能在本作 ROM 上建立本 session
自己的 GDB listener；若不能，保留精確 infrastructure boundary，避免把 socket 失敗
誤寫成 reader／VRAM consumer 未命中。

## 已確認的 listener ownership

- port `2345` 已由其他 mGBA process 監聽，未連線、未停止、未重用。
- port `23901` 沒有 listener；先前 M37 專用 A9PJ build 在建立 socket 時回報
  `Debugger: Couldn't open socket`。
- 本次只啟動指向 `/private/tmp/project-atlantis-a9pj.gba` 的本 session process；
  自己的 process 結束後以 Ctrl-C 停止，沒有碰其他 ROM 或 session。

## 替代啟動結果

使用本機既有標準 mGBA／SDL binary，沒有重新編譯或修改 mGBA source：

1. `/opt/homebrew/bin/mgba -g` 配合既有 `/private/tmp` port rewrite wrapper：GUI
   pasteboard／headless environment 先退出，沒有產生 GDB listener。
2. 既有 standard SDL build 配合 port rewrite wrapper，導向獨立 port `24567`：
   stdout 為 `Debugger: Couldn't open socket`，`24567` 無 listener。
3. 同一既有 standard SDL build 配合 Darwin interpose shim，導向獨立 port
   `25351`：stdout 同為 `Debugger: Couldn't open socket`，`25351` 無 listener。

三次都沒有送出 GDB packet、沒有寫入遊戲 state／RAM／VRAM，也沒有進入 text reader
或 keyboard transition；因此本 receipt 的 runtime hit 應分類為
`startup-listener-unavailable`，不是 `reader_breakpoint_hit=false` 的文字證據。

## 邊界判定

| 欄位 | M39 結果 |
| --- | --- |
| clean ROM identity | 未進入 runtime；輸入固定 A9PJ path |
| own listener 24567／25351 | `0/2` |
| other listener interference | `false`；2345 未觸碰 |
| text consumer／caller hit | `not observed`，非 negative |
| BG／VRAM／DMA receipt | `not attempted` |
| existing bounded eligible rows | `2`（M32/M34，未擴張） |

因此 M39 不改變 M35/M38 的 known-screen ledger gate，也不阻塞既有 source hash、
restore／strip、Latin relocation／BPS POC。下一步只接受新的獨立 fixed-screen
record／tilemap proof 或可用的 runtime listener；不再盲目重試同一 socket 啟動。

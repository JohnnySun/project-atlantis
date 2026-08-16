# M2 fixed parser/caller runtime probe（2026-08-16）

## 範圍

本回合只把已完成的 static parser/caller contract 收斂成一個 bounded runtime
probe，沒有再做 pointer scan、font geometry 或 state/object override。工具是
[`tools/parser_record_runtime_probe.py`](../tools/parser_record_runtime_probe.py)，
由 [`tools/m18_a1ac_probe.py`](../tools/m18_a1ac_probe.py) 在正常 state 4→7 return
後，以同一個 GDB connection 呼叫；transport 仍是共用的
[`core/gba/gdbstub_client.py`](../../../core/gba/gdbstub_client.py)。

固定觀察點只有：

- parser entry `0x080025CC`；caller LR 只接受已審核的 direct callsites
  `0x0800164C`、`0x08001D92`、`0x08001E26`、`0x0800281C`；
- IWRAM cursor global `0x03001588`，只讀一個 bounded word 作 metadata；
- parser/caller 的 `r1` 只對 exact strict record start 分類，命中後才安裝該筆
  ROM source read-watchpoint；
- parser `r0` 若是 GBA RAM pointer，只安裝一個 bounded write-watchpoint，標籤
  為 output candidate；
- `0x08001DBC` 只作 IWRAM writer entry breakpoint，不把它當作 VRAM writer。

輸出只有 stop PC/LR、寄存器 snapshot、pointer classification、address、hash／
count 與錯誤類型；不輸出 source、RAM、glyph、VRAM bytes、圖片或完整日文。每次
sequence 受 `max_events`、`max_stops`、`max_parser_hits` 與 per-event timeout
限制，unexpected stop 立即結束，所有 watchpoints/breakpoints 在 finally 移除。

## Confirmed

- parser/caller 的 offline contract、exact strict boundary、RAM／ROM 分類與
  metadata-only output 有離散測試。
- `m18_a1ac_probe.py` 已提供 mutually-exclusive
  `--trace-parser-after-return` mode；它只在同一連線取得正常 state return 後才
  移除 M1.8 固定 breakpoints，接著啟動 parser probe。
- B3TJ ROM identity 在本次 runtime invocation 先通過：title `TOWNARIKIRI3`、
  game code `B3TJ`、maker `AF`、size `16777216`、clean CRC32 `1867CCEF`。

## Negative / unknown

- 本次 fresh standard mGBA 的 parser invocation 使用 bounded
  `none:64,a:8,none:56` sequence；client 在 GDB socket setup 得到
  `PermissionError: [Errno 1] Operation not permitted`，因此
  `termination=setup-error`、state return/parser/source/output/writer/key event
  都是 `0`。這是本機 socket permission boundary，不是 parser、menu 或文字
  consumer 的 runtime negative；沒有取得 parser hit、strict source read、RAM
  decoder、glyph 或 VRAM 因果證據。
- 低權限 client 失敗後沒有用替代 transport 或其他 session 繞過隔離；本次自有
  B3TJ mGBA process 已停止。下次應在獲准的同一連線 runtime lane 重跑，不應把
  setup failure 當作遊戲沒有文字。
- 目前仍不能宣稱 `0x080025CC` 會收到五窗 strict source pointer，也不能宣稱
  parser output 是 decoder、`0x08001DBC` 是 VRAM writer、Shift-JIS 是 runtime
  codepage，或已確認 glyph identity／控制碼。

## 可重跑命令

先啟動本作自有、可確認 ownership 的 mGBA GDB listener，再以同一 process／同一
GDB connection 執行：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/m18_a1ac_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <independent-b3tj-gdb-port> --per-stop-timeout 30 \
  --max-stops 64 --max-edge-checks 8 --release-reads 3 --max-steps 12 \
  --trace-parser-after-return --parser-sequence none:64,a:8,none:56 \
  --parser-max-events 128 --parser-max-stops 64 --parser-max-hits 8 \
  --parser-per-event-timeout 5 \
  --output /private/tmp/tow-nd3-m18-parser-runtime.json
```

只有當 `parser_hits` 的 `r1_input.status` 是 `strict-record-start`，且後續
`source_read_hits` 實際命中，才可進入下一個最小切片：沿該次 source-reader
PC/LR 追一層 RAM decoder/output；parser entry、RAM candidate、writer entry 或
asset address 單獨都不足以完成 M2 live consumer。

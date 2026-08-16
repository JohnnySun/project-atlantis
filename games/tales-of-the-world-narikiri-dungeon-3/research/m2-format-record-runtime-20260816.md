# M2 bounded format-loop strict-record runtime probe（2026-08-16）

## 範圍

本回合只把已確認的 formatter／font static edge 收斂成一個可重跑的 runtime
listener。工具是 [`tools/format_record_runtime_probe.py`](../tools/format_record_runtime_probe.py)，
共用 GDB transport 是 `core/gba/gdbstub_client.py`；本作不新增 port shim，也不
修改其他遊戲。

probe 的唯一入口 breakpoint 是 `0x080014F4`。每次命中都先用 strict extractor
metadata 將 `r0` 分成：exact strict record start、strict-window non-start、window
外或非 ROM pointer。只有 exact record 才能安裝該筆 source read-watchpoint；預設
目標是 `sjis:0x146EE0`，`--trace-first-strict` 只允許第一個實際命中的 strict
record 取代預設目標。這避免把資源 pointer、record interior 或地址相近值升格成
文字來源。

## Bounded stage contract

命中 exact record 後，probe 依序只允許下列有限證據：

1. source record 的 read-watchpoint（只記 stop PC/LR、寄存器與 RAM destination
   candidates，不輸出 bytes）；
2. `0x08004D90` codepoint lookup entry 的寄存器 snapshot；
3. `0x08001414` font-map entry 的 `r2` index，依已審核的
   `0x080DDCC4 + r2*0x20` 公式做 ROM-bound check；
4. 一個 0x20-byte asset slot read-watchpoint；
5. 最多一次 `0x080011A8`／`0x080012E0` transform entry 與
   `0x03000560` scratch write。

每個 stage 都有 timeout／stop limit，unexpected stop 立即結束；KEYINPUT stop 只
保留 bounded input write receipt。輸出只有 address、register、caller LR、分類、
hash/count、stop status 與錯誤類型，raw source/glyph/RAM/VRAM/image 仍只留在
ignored work 或 `/private/tmp`。

## 驗證結果

### Confirmed

- 工具只使用 `core/gba/gdbstub_client.py`，不擴大 pointer/resolver scan。
- exact strict record classification、reviewed formatter caller LR、asset address
  bounds 與 metadata-only output 有離散測試。
- 本作測試：`76` tests passed；core/gba：`6` tests passed。
- ROM identity／strict input load：`B3TJ`、CRC32 `1867CCEF`、`8938` high-quality
  records。

### Provisional

- `0x080014F4 → 0x08004D90 → 0x08001414 → asset → scratch` 仍是由 static
  disassembly 與 bounded probe contract 串起的候選 runtime chain。
- selected record 的 code-unit→lookup-result→asset arithmetic 仍只來自
  [`m2-static-record-font-path-20260816.md`](m2-static-record-font-path-20260816.md)，
  不是 live register/read receipt。

### Negative / unknown

- 早先受 sandbox 限制的 bounded invocation 在 GDB socket setup 收到
  `PermissionError`；報告為 `termination=setup-error`、`format_hits=0`、
  source/lookup/asset/scratch hits 全為 `0`。這不是 runtime code path negative。
- 以乾淨 standard SDL/GDB mGBA、明確自有的 `127.0.0.1:2345` listener 從 reset
  實際重跑 formatter sequence：initial stop `S02`、KEYINPUT events `72`
  （start 12、none 48、A 12）、`termination=sequence-exhausted-without-strict-record-format-hit`，
  `format_hits=0`。這是該 bounded startup sequence 的 confirmed runtime
  negative，但不是 state 7 全部畫面的 negative。
- 另以同一 standard process 先完成 M1.8 正常 state 4→7，再開第二個 GDB
  connection 執行 formatter；mGBA 0.10 stub 對 `qSupported` timeout，沒有取得
  formatter hit。這是 known single-client lifecycle limitation，不是 source
  read／decoder／glyph 的 negative；其他遊戲 listener 未接管、未停止。
- 修正後以 `m18_a1ac_probe.py --trace-format-after-return` 在**同一 GDB
  connection**完成正常 state 4→7，再執行 `none:64,a:8,none:56`／128-event
  formatter stage；`0x080014F4` hit、strict source read、lookup、asset、scratch
  全為 `0`，termination 是 bounded sequence exhausted。這關閉了 second-client
  lifecycle 缺口，但只是否定這一個 state 7 sequence，不是否定其他 menu/event。
- 目前不能宣稱 Shift-JIS 是 runtime codepage、不能確認 glyph identity／寬度、
  不能把 asset read 當成文字 record 消費，也不能開始翻譯。

## 重跑

須使用本作自己啟動且確認 ownership 的 mGBA GDB port；不要連接其他遊戲或其他
session 的 listener：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/format_record_runtime_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> \
  --max-events 64 --max-format-hits 8 --max-stage-stops 12 \
  --output /private/tmp/tow-nd3-format-record-runtime.json
```

若 state 7 正常流程沒有選到預定 record，可加 `--trace-first-strict`；該 fallback
仍只接受實際命中的 strict record。只有取得 source read hit 後，才可把下一個最小
切片縮到該次 source reader 的 caller／RAM decoder；在此之前不增加 geometry、
pointer scan 或翻譯工作。

注意：mGBA 0.10.x 常在第一個 GDB client disconnect 後不接受第二個 connection。
要驗證「正常 state 4→7 後的 formatter」時，使用 m18 的
`--trace-format-after-return` 合併 mode；單獨先跑 m18 再重新連線不足以構成該
state 7 trace。合併 mode 已取得上述 bounded negative，下一步不是增加 formatter
events，而是窄追 `0x080025CC` parser/caller。

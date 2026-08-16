# A9PJ M44 headless consumer-breakpoint boundary（2026-08-16）

M44 是一次單通道、一次 process 的 debugger-capability check。它沿 M40 私有
headless Lua bridge 與相同按鍵 schedule，只額外嘗試在 `0x080063E0` null-terminated
consumer 設一個 software breakpoint；不送 GDB packet、不寫遊戲 memory、不碰其他
session。Lua script 與完整 log 留在 `/private/tmp`。

## Receipt

| 欄位 | result |
| --- | --- |
| ROM | A9PJ SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| breakpoint target | `0x080063E0`，單一 consumer cohort |
| Lua `emu:setBreakpoint` id | `-1` |
| breakpoint hits | `0` |
| Lua watchpoint ids | EWRAM／font-record／BG0 tile `-1/-1/-1` |
| runtime gate | frame 1500／2100／2700 均 `DISPCNT=1B40`、`BG1CNT=0106`、keyboard entry `8/8` |
| code-unit sequence | `0x005E→0x0062→0x0066` at frames `662→1202→1742` |
| runtime tile hashes | `b5ae4440…c1ff39c2`／`924e2894…293c19f7`，與 M19/M40 相同 |

`emu:setBreakpoint` 在沒有 `-g`／attached debugger module 的 headless run 中回傳
`-1`，所以沒有 caller PC/LR、r2 source pointer 或 scene reader receipt。frame callback
中讀到的 PC/LR 仍只是 callback context，不列為 consumer evidence。

## 邊界判定

這不是「文字 consumer 未執行」的 negative，而是「本機 headless build 在未載入
debugger 時不能註冊 software breakpoint」的 capability negative。M39 已證明本 session
可用的 GDB listener fallback 在 socket startup 失敗；M44 再證明 headless polling
不能補上 breakpoint。兩條證據合併後，停止重試同一 debugger capability，不新增
M29+ candidate layer。

existing static／known-screen facts 不變：

- M1.7 `0x080063C7`→BG0 font-record CPU renderer 與 M40 BG1 keyboard asset 仍是
  `independent-renderers-correlated-by-code-unit-only`。
- M41/M42 的 bounded static UI mapping 仍不是 general codepage；M32/M34 的
  ledger-eligible rows 維持 `2`。
- M44 沒有新增 source row、translation row、control semantic 或 BPS；下一步應在
  已有固定 mapping／source-hash／Latin reinsertion POC 上做最小翻譯工程，並將
  non-UI／live-reader 缺口明確保留為未完成 QA。

## 可重跑命令

```sh
perl -e 'alarm 8; exec @ARGV' -- env \
  DYLD_LIBRARY_PATH=/private/tmp/atlantis-mgba-headless-build \
  /private/tmp/atlantis-mgba-headless-build/mgba-headless \
  -C logLevel=8 \
  --script /private/tmp/tow-headless-probe.lua \
  /private/tmp/project-atlantis-a9pj.gba \
  > /private/tmp/tow-headless-break-m44.log 2>&1
```

只需從 stdout/log 取 breakpoint id、hit count、stable gate、code-unit frame 與 tile
hash 欄位；不得將 raw log、ROM、RAM／VRAM dump 或圖片放入 repository。

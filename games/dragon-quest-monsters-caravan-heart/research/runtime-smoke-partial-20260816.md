# patched A9HJ runtime smoke（partial，2026-08-16）

這份 receipt 只記錄第七批 cumulative patched ROM 的 mGBA／GDB 有界 smoke trace；它不是
完整場景 QA，也沒有把未命中的 glyph／layout breakpoint 填成 pass。所有 RAM／VRAM raw
dump 與圖片都留在 `/private/tmp`，本檔只保存 hash 與控制流程摘要。

## 輸入與 process boundary

- clean A9HJ：SHA-256 `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- cumulative seven-batch patched ROM：SHA-256
  `ADFE497F3297C7431D2D1241C110328D12A13B2D1A66D9CA2CDBA34D3581993E`、target CRC32 `4021E5B1`
- mGBA：`0.10.5 ((unknown))`
- 只在 `/private/tmp/dqmch-mgba.JcHDF8/` 使用臨時 port-2543 binary；該副本 SHA-256
  `29C2134F5C23D20F64D8BA637BB73148FE91BE152F4E0B7EF8FE113BB0193BA7`
- 本 session 的 listener 曾使用 ephemeral GDB port `53136`，process PID `9378`；trace
  完成後已停止該 PID，2345 的其他 listener 未操作。

## Trace 結果

- GBA initial stop：`S02`。
- asset dispatch：`0x08000528`，source `0x0846EDCC`（ROM）→ destination `0x0600C000`
  （VRAM）；helper `e` 從 `0x0600BFFE` 到 `0x0600D53E`，長度 `5438`，輸出 SHA-256
  `2B321A94134C6B81658CD04DD405190B97509A65DFE33CF93829016CD5FF7DC1`。
- 兩次 input-poll 都收到 `0xFFFFFC00`，runtime 只覆寫自己的 r0 為 `0x000003FE`；未寫 ROM
  或 save。
- 第一次 A 後 I/O：`DISPCNT=0x0100`、`BG0CNT=0x1D0C`、BG1–BG3 為 0；第二次 A 後同樣
  保持此設定。
- 第二次 A 後命中 `0x08012500` text-parser 12 次；本次 bounded trace 沒有命中
  `0x0801266C`／`0x08013738`／`0x08013E00`／`0x08013E4C`，所以沒有新的 glyph identity
  或 layout pass。
- 同次較早的有界 VRAM dump 只渲染出 Enix 開機 logo（不是目標翻譯畫面）：VRAM SHA-256
  `0FDD5E16D85DF1DEB4890B039E3D2C7DA2B7457E81DA476927A62B165C09F70B`、palette
  `9885A43E84CC7827C06717AA5B620B919AC7EE65640C8D4CC6D2D9F4244035B6`、OAM
  `AC39C4BB2C8699336AA8227F31B1834079BFB5C70CD22CC0D2BD0ADC8478A3B1`、IWRAM
  `48081548FF83B549843BC09C1E8D2B97701A4D528F2FE2BEF58890B934A9D541`。

## QA 結論

`runtime_qa=partial`：patched ROM 的入口、資產搬移與 text-parser 可達；翻譯目標的穩定
menu／battle-start 畫面、glyph writer、字寬／VWF、控制碼與全場景 mGBA QA 仍未證明。
ROADMAP 的完整 mGBA QA gate 保持未完成。

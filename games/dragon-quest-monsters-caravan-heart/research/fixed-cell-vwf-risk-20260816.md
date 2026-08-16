# clean writer 的 fixed-cell／VWF 風險界線（2026-08-16）

`tools/audit_text_layout.py` 在 clean A9HJ 上新增兩個 output-index Thumb signatures：

- pair combiner `0x080137FE`：`ldrb state+0x16` → `+1` → `strb state+0x16`
- single glyph writer `0x08013E34`：`ldrb state+0x16` → `+1` → `strb state+0x16`

兩條路徑都以 `state[0x16]` 作 output slot index，再乘以由 `state[0x10].bit7` 選出的
32／64-byte glyph stride；沒有在這個 bounded writer receipt 中把 slot advance 解讀為
Unicode 字寬或完整 VWF cursor。`advance_model.bounded_vwf_status` 固定為
`not-proven; clean writer evidence is fixed-cell output-slot advance`。

這縮小了回插風險：目前可安全證明的是每個 glyph／pair 佔一個 output slot，及其 32／64-byte
tile copy；尚未證明字元實際螢幕寬度、換行／換頁、游標溢位、控制碼造成的 layout state，
也不能直接採用既有英文 patch 的 width table。下一個 encoder gate 仍需以 clean runtime
畫面與未修改 script round-trip 交叉驗證。

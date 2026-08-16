# A9HJ 控制碼參數消費邊界（2026-08-16）

這是一份 clean A9HJ 的靜態、無原文輸出 audit。它只驗證 dispatch handler 內的 Thumb
instruction signature、parser outer-loop 與 state 條件，不把任何 handler 名稱當成已完成
語義，也不把這些結果直接套進 extractor。

## 可重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_control_consumption.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba
```

工具先驗證 clean ROM 的 SHA-256
`FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`，再核對 24 個
source-read 與 4 個 context instruction signatures。它不讀 script pointer 指向的資料，
也不輸出 raw bytes 或任何日文原文。

## 結果

| shape | 控制碼 | 靜態意義 |
|---|---|---|
| `none` | `E2 E3 E5 E9 EA EB EC ED EE EF F1 F2 F3 F5 F6 F7 F8 FB FC FD FE FF` | handler 未在已固定的 source-pointer read path 取參數；完整 state／畫面語義仍未命名。 |
| `fixed-1` | `F0 F9` | `F0` 從 `state+0x18` 取一個邏輯 source byte，前進 pointer，寫入 handler state `+0x1C`；`F9` 的兩條 state branch 都會到共同 source read，前進 pointer 1，並把低 byte 寫入 handler state `+0x0F`；這些都不是字元 glyph。 |
| `conditional-1` | `DF E0 E1 E4 E6 E7` | 至少存在一個一 byte read path；這些 handler 受 `state+0x10.bit5`／`state+0x11.bit7` 分支影響，另一條路徑會使用既有 state 欄位而不取同一個 source byte。 |
| `conditional-2` | `E8 F4 FA` | 存在兩 byte path；`E8` 兩次取 source pointer byte，`F4/FA` 在 `state+0x17 == 0` 讀 little-endian `state+0x22`，否則處理既有 pending state。 |

`E0`／`E1` 在這張表只表示 control dispatch handler 的參數分支；它們另有已獨立證明
的 alternate glyph consumer：handler 會取一個 index byte，`E0`／`E1` 分別選擇
`0x082E0BD4` base／`+0x4000` bank。這兩層不可混為同一個「控制碼參數」。

## 解碼器邊界決定

目前 `tools/extract_text.py` 只將 `0x92/0x93` pair 與 `E0/E1` alternate-glyph 做已證明的
token grouping，其餘 `DF..FF` 保留為單 byte `control-candidate`。原因是 `DF/E0/E1/E4/E6/E7`
有 state-dependent alternate path，`E8/F4/FA` 有 conditional two-byte path；雖然 `F9` 的
source read 寬度已固定為 1，前後 state／版面語義仍未命名。若在沒有 runtime context 的
pointer-only extractor 內盲目吞參數，會破壞
pointer span 與後續可逆回插。下一個必要 gate 是把 control token 的 context／參數保存格式
與 parser loop 一起證明，之後才可將相應 rows 提升到 ledger。

## Parser／handler context correction

這一輪新增的 4 個 context signatures 讓兩個容易混淆的問題分開：

- parser `0x0801265A` 以 `state+0x10` bit 3 決定是否跳回 `0x0801251A` 繼續 outer loop；
  這是 consumer continuation，不是某個單一 control byte 的 terminator 定義。
- `F9` handler `0x0801334A` 先依 `state+0x10` bit 7 選擇是否交換 `state+0x0E`／
  `state+0x0F`，兩條路徑都會落到 `0x0801335A` 的 source pointer read，再將 pointer
  前進 1。故 F9 應記為 `fixed-1`，不能記為「只有 bit 7 設定時才讀 source」。
- `FF` handler `0x08013668` 不取 source byte。bit 5 path 會清理 `state+0x10` 的 flags；
  另一條 state+0x11 bit 7 path 會進入 `0x08013694`，清除包含 outer-loop bit 3 的
  flag 後回到共同 flush path。這證明 FF 會影響 continuation state，但仍不足以把 FF
  命名為固定 record terminator。

這些是 code-level context facts，不是 `F9`／`FF` 的遊戲語義；完整 jump、換頁、事件與
版面 contract 仍須由 caller／runtime／未修改內容 round-trip 共同證明。

## 邊界

這份 receipt 證明的是 source-pointer read shape 與有限的 continuation-state context，不是控制碼名稱、腳本終止符、換頁／換行、
字寬表或完整 VWF 語義；`FF` 仍不得單獨視為 record terminator。完整 codepage、全量
context decoder、回插與 runtime QA 仍未完成。

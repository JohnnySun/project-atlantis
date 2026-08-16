# A9HJ 控制碼參數消費邊界（2026-08-16）

這是一份 clean A9HJ 的靜態、無原文輸出 audit。它只驗證 dispatch handler 內的 Thumb
instruction signature 與 state 條件，不把任何 handler 名稱當成已完成語義，也不把這些
結果直接套進 extractor。

## 可重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_control_consumption.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba
```

工具先驗證 clean ROM 的 SHA-256
`FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`，再核對 24 個
source-read instruction signatures。它不讀 script pointer 指向的資料，也不輸出 raw bytes
或任何日文原文。

## 結果

| shape | 控制碼 | 靜態意義 |
|---|---|---|
| `none` | `E2 E3 E5 E9 EA EB EC ED EE EF F1 F2 F3 F5 F6 F7 F8 FB FC FD FE FF` | handler 未在已固定的 source-pointer read path 取參數；完整 state／畫面語義仍未命名。 |
| `fixed-1` | `F0` | 從 `state+0x18` 取一個邏輯 source byte，前進 pointer，寫入 handler state `+0x1C`；這不是字元 glyph。 |
| `conditional-1` | `DF E0 E1 E4 E6 E7 F9` | 至少存在一個一 byte read path；`DF/E0/E1/E4/E6/E7` 受 `state+0x10.bit5`／`state+0x11.bit7` 分支影響，`F9` 只在 `state+0x10.bit7 == 1` 取 source pointer。 |
| `conditional-2` | `E8 F4 FA` | 存在兩 byte path；`E8` 兩次取 source pointer byte，`F4/FA` 在 `state+0x17 == 0` 讀 little-endian `state+0x22`，否則處理既有 pending state。 |

`E0`／`E1` 在這張表只表示 control dispatch handler 的參數分支；它們另有已獨立證明
的 alternate glyph consumer：handler 會取一個 index byte，`E0`／`E1` 分別選擇
`0x082E0BD4` base／`+0x4000` bank。這兩層不可混為同一個「控制碼參數」。

## 解碼器邊界決定

目前 `tools/extract_text.py` 只將 `0x92/0x93` pair 與 `E0/E1` alternate-glyph 做已證明的
token grouping，其餘 `DF..FF` 保留為單 byte `control-candidate`。原因是 `DF/E0/E1/E4/E6/E7`
有 state-dependent alternate path，`E8/F4/FA` 有 conditional two-byte path，`F9` 也不是
每次都讀 source；若在沒有 runtime context 的 pointer-only extractor 內盲目吞參數，會破壞
pointer span 與後續可逆回插。下一個必要 gate 是把 control token 的 context／參數保存格式
與 parser loop 一起證明，之後才可將相應 rows 提升到 ledger。

## 邊界

這份 receipt 證明的是 source-pointer read shape，不是控制碼名稱、腳本終止符、換頁／換行、
字寬表或完整 VWF 語義；`FF` 仍不得單獨視為 record terminator。完整 codepage、全量
context decoder、回插與 runtime QA 仍未完成。

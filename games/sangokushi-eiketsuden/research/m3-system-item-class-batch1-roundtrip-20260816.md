# M3 system-item/class batch 1：bounded item-description round-trip

日期：2026-08-16（Asia/Taipei）

本批次開始處理 pool A（decoder 對應 `system-item-class`）的短 item／class
description。只選 4 個已確認上下文、固定槽位可容納的 records；完整日文原文、ROM、
work、generated planes、patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/system-item-class-batch-1.jsonl` 有 4 筆 source-free rows：entries `003`、
  `004`、`055`、`056`。每筆有 source hash、兩行 `zh-TW` target、上下文、max width、
  控制碼清單、術語欄位和 `ai_review`；restore→strip 逐 byte 相同，schema pass，source
  fields `0`。
- system-item-class pool boundary 是 file base `0x0CBC54`、183 entries；本批次 4 個
  unique targets，selected aliases 展開為 5 entries。未選取 records byte-identical，
  pointer table 不變，ROM size 保持 `4194304` bytes。
- target 只有 `U+6548`（效）使用 licensed custom glyph map；custom glyph plane match
  `1/1`，selected re-extract `5/5`、fixed-slot `5/5`，changed bytes `161`。其餘 target
  characters 走 strict Shift-JIS；format／control-byte invariant 保持不變。
- clean ROM SHA-256 為 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；
  patched／BPS-applied ROM SHA-256 均為
  `5e6bb05a21fd4c1b26f5cac1fd9475329fe082554025a9051516d27ece05dfb7`。
- system-item-class batch 1 BPS：`220` bytes；source CRC32 `a4a1c956`、target CRC32
  `64b494f2`、patch CRC32 `0cd7c391`；BPS SHA-256
  `a27b0b81cd72358a8b65e73e4635454f3660c1a8d7a6b18ad547484e46902391`。套用後與 custom
  patch output `cmp` 相等。

## provisional／pending

- pool A 仍有 149 unique source records，這一批只覆蓋 4 個 description records；其餘
  item／class、策略效果、兵種轉換和兩行版面尚未翻譯／QA。
- `持有即可生效`、`自然恢復` 等 wording 仍為 `ai_review`，需 item screen 的自然畫面
  核對與臺灣術語審核。custom raw code unit non-use 仍只限四池 decoded source table。
- 本批次證明 selected pool-A record／custom glyph layer 的 fixed-slot round-trip，不是
  全 pool A、全字庫、全版面或自然 runtime 完成證明。

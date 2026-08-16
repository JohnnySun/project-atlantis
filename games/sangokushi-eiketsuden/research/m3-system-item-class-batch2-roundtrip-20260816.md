# M3 system-item/class batch 2：class-conversion description round-trip

日期：2026-08-16（Asia/Taipei）

本批次延伸 pool A 的 class-conversion descriptions，選 entries `000`、`001`、`002`、
`016`、`017`、`018` 六個 unique records。完整日文原文、ROM、work、generated planes、
patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/system-item-class-batch-2.jsonl` 有 6 筆 source-free rows；每筆有 source
  hash、兩行 `zh-TW` target、上下文、max width、控制碼清單、術語欄位和 `ai_review`；
  restore→strip 逐 byte 相同，schema pass，source fields `0`。
- system-item-class pool boundary 保持 file base `0x0CBC54`、183 entries；本批次 6 個
  unique targets，selected entries `6/6`，pointer table 不變，未選取 records byte-identical，
  ROM size保持 `4194304` bytes。
- custom-aware encoder 使用 `U+5C07`、`U+8B8A`、`U+70BA`、`U+6A02`、`U+8F15` 的
  licensed mapping；custom glyph plane match `5/5`，selected re-extract `6/6`、fixed-slot
  `6/6`，changed bytes `455`；format／control-byte invariant 保持。
- clean ROM SHA-256 為 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；
  patched／BPS-applied ROM SHA-256 均為
  `fba2f354ff1905beddc3c72487733db8efda3832ecf5e8714f1bd3b322c39dab`。
- system-item-class batch 2 BPS：`565` bytes；source CRC32 `a4a1c956`、target CRC32
  `c6e49fa8`、patch CRC32 `58005e2e`；BPS SHA-256
  `2f47ea59b9435dfc72ae155fb142584eaab0c06cd1a75d63e0ae0ceced03839e`。套用後與 custom
  patch output `cmp` 相等。

## provisional／pending

- pool A 的 class-conversion wording 仍為 `ai_review`；`妖術使`、`輸送隊`、`軍樂隊`、
  `輕騎兵` 等臺灣兵種用語需 item／class 畫面核對與術語人工審核。
- 目前 pool A 累計覆蓋 10 個 unique records；其餘 139 個 unique records、更多兩行
  descriptions、版面／字距和自然 item screen runtime 仍 pending。
- custom raw code unit non-use 只限四池 decoded source table；本批次不宣稱 full-ROM
  safety、全池回插或自然 reachability。

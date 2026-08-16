# M3 system-item/class batch 3：level-gated class conversion round-trip

日期：2026-08-16（Asia/Taipei）

本批次處理 pool A 的 level-gated class conversions與 additional class descriptions，
選 entries `019`–`026`、`078`–`081` 共 12 個 unique records。完整日文原文、ROM、work、
generated planes、patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/system-item-class-batch-3.jsonl` 有 12 筆 source-free rows；每筆有 source
  hash、兩行 `zh-TW` target、上下文、max width、控制碼清單、術語欄位和 `ai_review`；
  restore→strip 逐 byte 相同，schema pass，source fields `0`。
- system-item-class pool boundary 保持 file base `0x0CBC54`、183 entries；12 個 unique
  targets、selected entries `12/12`，pointer table 不變，未選取 records byte-identical，
  ROM size保持 `4194304` bytes。
- custom-aware encoder 使用 8 個 licensed mapping glyphs；custom glyph plane match `8/8`，
  selected re-extract `12/12`、fixed-slot `12/12`，changed bytes `812`；format／control-byte
  invariant 保持。
- clean ROM SHA-256 為 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；
  patched／BPS-applied ROM SHA-256 均為
  `bc895d7dfb8529ccb0e733034709dd92a3afe0dbba0e7f28e9afadfcc8c28bfb`。
- system-item-class batch 3 BPS：`973` bytes；source CRC32 `a4a1c956`、target CRC32
  `4fbe6c36`、patch CRC32 `231c8389`；BPS SHA-256
  `8448c1151be5f4a794064723ac98cc8df837ae9dbd356c731d51e059bdc43bdc`。套用後與 custom
  patch output `cmp` 相等。

## provisional／pending

- `投石車` 對日文 `発石車` 的臺灣用語仍需公開來源與畫面核對；其他兵種 conversion
  wording 也仍為 `ai_review`，不可當成最終術語。
- pool A 累計覆蓋 22 個 unique records；其餘 127 個 unique records、更多兩行 descriptions、
  item／class 版面和自然 runtime 仍 pending。
- custom raw code unit non-use 只限四池 decoded source table；本批次不宣稱 full-ROM
  safety、全池回插或自然 reachability。

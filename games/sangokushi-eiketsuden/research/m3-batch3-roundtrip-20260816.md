# M3 Table B batch 3：withheld 經驗 label custom-glyph round-trip

日期：2026-08-16（Asia/Taipei）

本批次只處理 Table B 尚未覆蓋的 1 個 unique record B20。它使用明確的臺灣繁體
`經／驗` custom mapping；沒有採用日文 `経／験` 代替，也沒有把 custom raw code unit
誤當成標準 Shift-JIS Unicode。完整日文原文、ROM、work、generated planes、patched
ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/table-b-batch-3.jsonl` 有 1 筆 source-free row `b3ej:table-b:020`，
  保留 source hash、`zh-TW` target、上下文、max width、控制碼清單和 `ai_review`；
  restore→strip 逐 byte 相同，schema pass，source fields `0`。
- custom-aware encoder 使用 `U+7D93`／`U+9A57` 的既有 raw code units 與 codepage
  indices `1833`／`617`，其他 target characters 走 strict Shift-JIS。兩個 custom glyph
  plane 全部 match，selected re-extract `1/1`、fixed-slot `1/1`，changed bytes `120`；
  44-entry pointer table、codepage table 和 ROM size 都不變。
- clean ROM SHA-256 為 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；
  patched／BPS-applied ROM SHA-256 均為
  `a8853a4cb529a78103c3fe4b0bb617c42dde1cfb5b174411b1091be6071d8c66`。
- Table B batch 3 BPS：`186` bytes；source CRC32 `a4a1c956`、target CRC32 `0fe59122`、
  patch CRC32 `8ab07150`；BPS SHA-256
  `419624c1cd99958d2d45ae521078ca29a5485ad09c37ad127447b69139534120`。套用後與
  custom patch output `cmp` 相等。

## provisional／pending

- Table B 現已覆蓋 26/26 unique records，但所有 batch 仍是 `ai_review`；B20 的 battle
  wording、單行寬度與 custom glyph 可讀性需自然戰役／策略畫面核對。
- custom mapping 的 raw code unit non-use 僅由 bounded decoded source pools 支持；
  仍未完成全 ROM 文本使用證明、自然 runtime glyph receipt、全池 round-trip、完整
  版面與其他 pool 翻譯。

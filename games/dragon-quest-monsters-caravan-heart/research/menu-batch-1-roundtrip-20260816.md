# bounded menu-batch-1 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ 的一個固定 title-menu span proof，不是全遊戲完成報告。所有 ROM、
source-bearing JSONL、patched ROM、BPS 與 JSON receipt 均留在 ignored `roms/`、ignored
`work/` 或 `/private/tmp`；本文件不保存完整日文原文或 ROM 內容。

## 輸入與界線

- clean input：8,388,608 bytes；SHA-256
  `fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce`；CRC32
  `3C24ABCC`。
- ledger row：`dqmch:a9hj:g06:v00:m0000`，source hash
  `222553bb3def3cd3da7d145bbf487c2fef8b20fe55b5ceaa3b73625f4f934e8f`；source-bearing
  restore copy 只在 `work/menu-batch-1.jsonl`。
- 原始固定 span：file offset `0x28647C`、46 bytes；原 span SHA-256
  `39a92ad7e4a4f39ecc62468878ed5f629e8e8e9f46f655445506d982145bbc70`。
- patched target：zh-TW `從頭開始  繼續遊戲  通訊對戰  三連戰`；44 bytes target data
  後保留 `FF FF`。
- 字庫：14 個由工具內明確撰寫的 8×8／GBA 4bpp tile，配置到 clean extractor corpus
  證明未使用的 E1 alternate-glyph slots；沒有匯入外部或未授權字型。

## 可重現結果

1. `restore_translations.rb` 產生 local `work/menu-batch-1.jsonl`。
2. `strip_translations.rb` 產生 source-free ledger；與追蹤的
   `translations/menu-batch-1.jsonl` `cmp` 完全一致。
3. `tools/patch_menu.py` 驗證 clean ROM、ledger/source hash、固定 span 與 E1 slot
   未使用條件後產生 patched ROM：
   `16737072f4073ac2869c120a53d9b95098b22249d570c22389ba9eeb1e75a555`。
4. `tools/verify_menu_patch.py` 重新解碼固定 menu span 回目標字串；patched ROM 與 clean
   ROM 的差異為 489 bytes，所有差異均在 14 個字形 tile range 或 46-byte menu span，
   outside-range changes 為 0。
5. `core/patches/bps_create.rb` 產生 534-byte BPS：
   `138abf5015a5f448f7b6542133c7f7311b6d18efd7cd014e5eb740ad67c8f839`；BPS header
   receipt 為 source CRC32 `3c24abcc`、target CRC32 `1739bf81`、patch CRC32
   `462b43e6`。
6. `core/patches/bps_apply.rb` 套用後的 8 MiB ROM 與 patched target `cmp` 完全一致，
   SHA-256 同為上述 `16737072…a555`。

## QA 邊界

- 遊戲專屬工具測試：24 tests，全部通過。
- shared `core/gba` 測試：20 tests，全部通過。
- source-free `translations/menu-batch-1.jsonl` 以 `schemas/localization-ledger.schema.json`
  驗證通過；local `work` copy 目前會被既有 `schemas/localization-record.schema.json`
  以 `decoder_version` 額外欄位拒絕，因此沒有把這個 bounded row 宣稱為完整 schema gate，
  也沒有跨範圍修改 shared schema。
- 這次 receipt 是 bounded static re-extraction／BPS proof；mGBA patched-ROM runtime
  QA 尚未執行，不能把 menu encoder 視為已核准，也不能據此宣稱完整 codepage、VWF、
  control semantics、全量 script round-trip 或完整翻譯已完成。

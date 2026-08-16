# M3 system-item/class batch 5：戰鬥狀態效果 round-trip

日期：2026-08-16（Asia/Taipei）

本批次處理 pool A `system-item-class` 的 6 個通用戰鬥效果 records：entries
`108`、`109`、`110`、`112`、`114`、`115`。沒有在本批次猜測或翻譯帶引號的策略專名；
完整日文原文、ROM、work、patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`，
本檔只保存 hash、offset、計數與可重跑命令。

## confirmed

- `translations/system-item-class-batch-5.jsonl` 有 6 筆 source-free rows；每筆有 source
  text hash、短版 `zh-TW` target、上下文、max width、控制碼清單、術語欄位和 `ai_review`。
  `restore_translations.rb` → `strip_translations.rb` 逐 byte 相同，source fields 為 `0`。
- system-item-class pool boundary 保持 file base `0x0CBC54`、183 entries；6 個 selected
  entries 對應 6 個 unique targets，pointer table 不變，未選取 records byte-identical。
- existing codepage coverage 為 `6/6`，原始固定槽位 fit 為 `6/6`；目標沒有新增 custom glyph。
  固定槽位 patch 改變 `114` bytes，沒有 relocation。
- custom-aware verifier 的 selected re-extract／fixed-slot 為 `6/6`；pool-level pointer table、
  codepage table 和未選取 records 均保持 byte-identical。
- clean ROM SHA-256 為
  `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched／BPS-applied
  ROM SHA-256 均為
  `30e8d7bdc499e14162085051c6c10674f3c20e7d5931e7d8ec9a48d7b925b410`。
- system-item-class batch 5 BPS：`167` bytes；source CRC32 `a4a1c956`、target CRC32
  `632d9602`、patch CRC32 `cef2cb2c`；BPS SHA-256
  `0dffb017f7de40474efcdb8b2c895cb4e72a6e9b49e9cb3cf363e93ae20dc8b1`。套用後與 custom
  patch output `cmp` 相等。

## provisional／pending

- `失序`、`恢復正常`、`回到未行動`、`吸取敵方耐久`、`策略小／大回復` 先沿用已審核的
  Table B battle-effect wording，仍是 `ai_review` 候選；未在自然 item／battle screen
  核對行寬、狀態名稱和玩家可見語境。
- pool A 累計覆蓋 34 個 unique records；其餘 pool A unique records、帶策略專名的戰鬥
  描述、完整 item／class 畫面、自然 runtime glyph receipt 和全池回插仍 pending。
- existing codepage coverage 只表示 codepage／slot 存在，不表示自然畫面已可達或 glyph
  美術品質已完成；本批次沒有新增 custom glyph，也不改變 full-ROM non-use 結論。

## reproducible bounded commands

```text
ruby core/ledger/restore_translations.rb \
  games/sangokushi-eiketsuden/translations/system-item-class-batch-5.jsonl \
  /private/tmp/b3ej-all-source-v3.jsonl \
  games/sangokushi-eiketsuden/work/system-item-class-batch-5.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/font_coverage.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work games/sangokushi-eiketsuden/work/system-item-class-batch-5.jsonl \
  --output /private/tmp/b3ej-system-item-class-b5-coverage.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba --pool system-item-class \
  --work games/sangokushi-eiketsuden/work/system-item-class-batch-5.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-a-b5.gba \
  --metadata-output /private/tmp/b3ej-a-b5.patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba /private/tmp/b3ej-a-b5.gba \
  --pool system-item-class --work games/sangokushi-eiketsuden/work/system-item-class-batch-5.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-a-b5.verify.json
ruby core/patches/bps_create.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-a-b5.gba /private/tmp/b3ej-system-item-class-b5.bps
ruby core/patches/bps_apply.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-system-item-class-b5.bps /private/tmp/b3ej-a-b5-applied.gba
cmp /private/tmp/b3ej-a-b5.gba /private/tmp/b3ej-a-b5-applied.gba
```

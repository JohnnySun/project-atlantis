# M3 system-item/class batch 4：耐久恢復描述 round-trip

日期：2026-08-16（Asia/Taipei）

本批次處理 pool A `system-item-class` 的 6 個唯一耐久恢復 records：entries
`027`、`031`、`032`、`046`、`047`、`048`。完整日文原文、ROM、work、patched ROM、BPS
和 extractor 輸出均留在 ignored／`/private/tmp`；本檔只保存 hash、offset、計數與可重跑
命令，不保存原文。

## confirmed

- `translations/system-item-class-batch-4.jsonl` 有 6 筆 source-free rows；每筆有 source
  text hash、兩行 `zh-TW` target、上下文、max width、控制碼清單、術語欄位和 `ai_review`。
  `restore_translations.rb` → `strip_translations.rb` 逐 byte 相同，source fields 為 `0`。
- system-item-class pool boundary 保持 file base `0x0CBC54`、183 entries；6 個 selected
  entry 對應 6 個 unique target，pointer table 不變，未選取 records byte-identical。
- existing codepage coverage 為 `6/6`，原始固定槽位 fit 為 `6/6`；目標只使用已存在的
  codepage／glyph slots，custom glyph count 為 `0`。固定槽位 patch 改變 `195` bytes，
  沒有 relocation。
- custom-aware verifier 由 pointer alias 展開後取得 selected re-extract／fixed-slot
  `31/31`；pool-level pointer table、codepage table 和未選取 records 均保持 byte-identical。
- clean ROM SHA-256 為
  `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched／BPS-applied
  ROM SHA-256 均為
  `699add018b3026c8d014d3b9c4c7f691f4b5df1bb2e39297a3ecf9990b03378e`。
- system-item-class batch 4 BPS：`257` bytes；source CRC32 `a4a1c956`、target CRC32
  `e4b23029`、patch CRC32 `c0b987dc`；BPS SHA-256
  `7ca7f5c6bf6c6efa24ab68c01dff31b712f54067c9e6258bc539820fc3e8dd66`。套用後與 custom
  patch output `cmp` 相等。

## provisional／pending

- 「一個／多個部隊耐久、少量／一定量／大量回復」是固定兩行、短槽位的 `ai_review`
  候選；尚未在自然 item screen 核對語氣、行寬與字面是否符合正式臺灣用語。
- pool A 累計覆蓋 28 個 unique records；其餘 pool A unique records、完整 item／class
  畫面、自然 runtime glyph receipt 和全池回插仍 pending。
- existing codepage 的 coverage 只表示 codepage／slot 存在，不表示自然畫面已可達或
  glyph 美術品質已完成；本批次沒有新增 custom glyph，也不改變 full-ROM non-use 結論。

## reproducible bounded commands

```text
ruby core/ledger/restore_translations.rb \
  games/sangokushi-eiketsuden/translations/system-item-class-batch-4.jsonl \
  /private/tmp/b3ej-all-source-v3.jsonl \
  games/sangokushi-eiketsuden/work/system-item-class-batch-4.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/font_coverage.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work games/sangokushi-eiketsuden/work/system-item-class-batch-4.jsonl \
  --output /private/tmp/b3ej-system-item-class-b4-coverage.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba --pool system-item-class \
  --work games/sangokushi-eiketsuden/work/system-item-class-batch-4.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-a-b4.gba \
  --metadata-output /private/tmp/b3ej-a-b4.patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba /private/tmp/b3ej-a-b4.gba \
  --pool system-item-class --work games/sangokushi-eiketsuden/work/system-item-class-batch-4.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-a-b4.verify.json
ruby core/patches/bps_create.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-a-b4.gba /private/tmp/b3ej-system-item-class-b4.bps
ruby core/patches/bps_apply.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-system-item-class-b4.bps /private/tmp/b3ej-a-b4-applied.gba
cmp /private/tmp/b3ej-a-b4.gba /private/tmp/b3ej-a-b4-applied.gba
```

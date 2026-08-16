# bounded message-batch-7 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ `g06/v00/m0040` 的第七筆有限批次，覆蓋 title-menu 的戰鬥開始詢問訊息。
source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored `work/`、`roms/`
或 `/private/tmp`，本 receipt 不保存完整日文原文。

## 固定輸入與 encoder boundary

- clean ROM：CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- source-free ledger：`translations/message-batch-7.jsonl`
- source hash：`4BDFFDB8D617207BCB4799BF05D73B879BDC4DA6FEACFB2A4C8FE256E86B19BF`
- fixed file span：`0x286756..0x286764`，15 bytes；最後 `FF` 為 terminator
- target：`要開始對戰嗎？`
- 新增 authored E1 glyph：`要=0xFC`、`嗎=0xFE`；重用 menu glyph：`開=0xD2`、`始=0xD3`、`對=0xDA`、`戰=0xDB`
- direct punctuation：`？=0x9B`

## 可重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_7.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-7.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-7.gba \
  --receipt /private/tmp/dqmch-message-batch-7-receipt.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_7.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-7.gba \
  --report /private/tmp/dqmch-message-batch-7-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-7.gba \
  /private/tmp/dqmch-message-batch-7.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-7.bps \
  /private/tmp/dqmch-message-batch-7-applied.gba

cmp /private/tmp/dqmch-message-batch-7.gba /private/tmp/dqmch-message-batch-7-applied.gba
```

## 結果

patched ROM SHA-256 為
`2D730C0981E9D436DD8F66D854695732142366564E76F200E4A4EA5BE9F0E617`；`verify_message_batch_7.py`
得到 `bounded_reextract=ok`、`allowed_range_count=7`、`changed_byte_count=206`、
`outside_range_changes=0`。BPS source CRC32 `3C24ABCC`、target CRC32 `29E68366`、
patch CRC32 `0F8A24C5`、patch size 254 bytes、BPS SHA-256
`45BBB1DDA34F25160610BE0DD45C6014396334E20593E969F573CB4E475A5CE1`；apply 後與 patched
ROM `cmp` 一致。`runtime_qa=not-run`，不能視為已完成的遊戲 QA。

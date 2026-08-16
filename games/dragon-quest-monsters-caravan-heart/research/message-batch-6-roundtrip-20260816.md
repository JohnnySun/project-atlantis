# bounded message-batch-6 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ `g06/v00/m0041` 的第六筆有限批次，覆蓋 title-menu 的戰鬥開始訊息。
source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored `work/`、`roms/`
或 `/private/tmp`；提交的 ledger 不含 `source` 欄位。

- clean ROM：8,388,608 bytes、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- string id：`dqmch:a9hj:g06:v00:m0041`
- clean fixed span：file `0x286765..0x286773`，14 bytes；原 span SHA-256
  `A82C772728E2AABF385156C79A487797D67B5AF06C234AB6069FF1B247E041C8`
- source hash：`AD8D4B95A7B01A690488DCBE72109E703381F3BE13DD28C21A9BC388820CD2F0`
- zh-TW target：`開始對戰。`
- preserved tail：最後 `FF` byte 保持不變；`0x94` 使用 clean direct full-stop glyph
- reused E1 slots：`D2` 開、`D3` 始、`DA` 對、`DB` 戰；四個 authored tiles 與第一批完全相同

## 重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_6.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-6.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-6.gba \
  --receipt /private/tmp/dqmch-message-batch-6.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_6.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-6.gba \
  --report /private/tmp/dqmch-message-batch-6-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-6.gba \
  /private/tmp/dqmch-message-batch-6.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-6.bps \
  /private/tmp/dqmch-message-batch-6-applied.gba

cmp /private/tmp/dqmch-message-batch-6.gba /private/tmp/dqmch-message-batch-6-applied.gba
```

## 結果

- verifier：`bounded_reextract=ok`、`allowed_range_count=5`、`changed_byte_count=141`、
  `outside_range_changes=0`、`runtime_qa=not-run`
- patched ROM SHA-256：`2585B04A7786AA517A5247F5C3EA7BD167FEB000661834313F37FBA6B353217B`
- target CRC32：`E06A2F4F`
- BPS：184 bytes、patch CRC32 `83B267A5`、SHA-256
  `50E93D46B09DDCF23D44AD0F016D38850376F0BF570CCEC7A8E076169DFEF2C5`
- BPS apply 後 `cmp`：`ok`

這仍是固定 span／重用手繪字形的靜態 proof；尚未證明完整 encoder、字寬／VWF、全量
ledger 或 mGBA runtime 畫面 QA。

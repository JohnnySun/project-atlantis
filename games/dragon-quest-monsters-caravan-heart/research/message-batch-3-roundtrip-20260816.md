# bounded message-batch-3 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ `g06:v00:m0006` 的第三筆有限批次，覆蓋 title-menu 通訊狀態列。
source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored `work/`、
`roms/` 或 `/private/tmp`；提交的 ledger 不含 `source` 欄位。

- clean ROM：8,388,608 bytes、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- string id：`dqmch:a9hj:g06:v00:m0006`
- clean fixed span：file `0x286533..0x286567`，53 bytes；原 span SHA-256
  `B5DE7859D81D77FCC67A945DCEDB1139068A26379620DFF7E5DF0978EF617CAF`
- source hash：`AD484C29A39BC4157B305202D8C92A45359253CB485E470573286E642A935986`
- zh-TW target：`連線狀態1P 確認中2P 確認中3P 確認中4P 確認中`
- preserved tail：最後 `FF` byte 保持不變
- E1 slots：`EB` 連、`EC` 線、`ED` 狀、`EE` 態、`EF` 確、`F0` 認、`F2` 中；
  均與前兩批及 clean extractor 使用集合不重疊

## 重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_3.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-3.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-3.gba \
  --receipt /private/tmp/dqmch-message-batch-3.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_3.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-3.gba \
  --report /private/tmp/dqmch-message-batch-3-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-3.gba \
  /private/tmp/dqmch-message-batch-3.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-3.bps \
  /private/tmp/dqmch-message-batch-3-applied.gba

cmp /private/tmp/dqmch-message-batch-3.gba /private/tmp/dqmch-message-batch-3-applied.gba
```

## 結果

- verifier：`bounded_reextract=ok`、`allowed_range_count=8`、`changed_byte_count=275`、
  `outside_range_changes=0`、`runtime_qa=not-run`
- patched ROM SHA-256：`58C200DCDDA0C45C569EE35B9A6BBF4142811AD7F6253C61ACE28FB9E4431193`
- target CRC32：`36E783B4`
- BPS：319 bytes、patch CRC32 `C4168E51`、SHA-256
  `9FDDE04277D662BF9F49F7B7A2A2071229AF54295B81D08051E6D88DEB163CC4`
- BPS apply 後 `cmp`：`ok`

這仍是固定 span／手繪字形的靜態 proof；尚未證明完整 encoder、字寬／VWF、
全量 ledger 或 mGBA runtime 畫面 QA。

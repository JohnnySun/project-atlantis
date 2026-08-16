# bounded message-batch-4 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ `g06/v00/m0044` 的第四筆有限批次，覆蓋 title-menu 通訊等待提示。
source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored `work/`、
`roms/` 或 `/private/tmp`；提交的 ledger 不含 `source` 欄位。

- clean ROM：8,388,608 bytes、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- string id：`dqmch:a9hj:g06:v00:m0044`
- clean fixed span：file `0x286792..0x2867A2`，16 bytes；原 span SHA-256
  `D32A41EC1D02FDA1BC07417E1664228EB0E1A00E0D564F246C6C989A48BE93DD`
- source hash：`DC2E9DFDAAA0258B17314006966AD71D1DA06BB5447E4C1A3C2EBBD3F21120C8`
- zh-TW target：`請稍候。`
- preserved tail：最後 `FF` byte 保持不變；`0x94` 使用 clean direct full-stop glyph
- E1 slots：`F3` 請、`F4` 稍、`F5` 候；均未被 clean extractor 使用，且與前面三批配置不重疊

## 重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_4.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-4.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-4.gba \
  --receipt /private/tmp/dqmch-message-batch-4.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_4.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-4.gba \
  --report /private/tmp/dqmch-message-batch-4-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-4.gba \
  /private/tmp/dqmch-message-batch-4.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-4.bps \
  /private/tmp/dqmch-message-batch-4-applied.gba

cmp /private/tmp/dqmch-message-batch-4.gba /private/tmp/dqmch-message-batch-4-applied.gba
```

## 結果

- verifier：`bounded_reextract=ok`、`allowed_range_count=4`、`changed_byte_count=111`、
  `outside_range_changes=0`、`runtime_qa=not-run`
- patched ROM SHA-256：`8BDB121B94C9FB37E1C5B08CE3555CFC22FB9D8CE78C2F2F6C0F4BE5ADCD05DB`
- target CRC32：`BBA93E10`
- BPS：150 bytes、patch CRC32 `E0CEC46E`、SHA-256
  `1404CA555340DD024E26B9C7883D66E84DE67DDA401F68D8DDC2F7898AFD03E3`
- BPS apply 後 `cmp`：`ok`

這仍是固定 span／手繪字形的靜態 proof；尚未證明完整 encoder、字寬／VWF、
全量 ledger 或 mGBA runtime 畫面 QA。

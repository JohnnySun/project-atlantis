# bounded message-batch-5 回插與 BPS receipt（2026-08-16）

這是 clean A9HJ `g06/v00/m0045` 的第五筆有限批次，覆蓋 title-menu 通訊等待訊息的兩行
fixed span。source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored
`work/`、`roms/` 或 `/private/tmp`；提交的 ledger 不含 `source` 欄位。

- clean ROM：8,388,608 bytes、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- string id：`dqmch:a9hj:g06:v00:m0045`
- clean fixed span：file `0x2867A2..0x2867C4`，34 bytes；原 span SHA-256
  `FE81501D3ADA312E3E57FE8E934F7F6960BCFC644429C08AC1082F33AC0F6B7F`
- source hash：`E9FC369D35C4E1577D91BDB6386F589A4A53C1C704E87F1AB1C9B9866ADB8C26`
- zh-TW target：`目前正在通訊中。請稍候。`
- preserved controls：中間 `FE` layout control 與最後 `FF` byte 保持不變
- E1 slots：新配置 `F7` 目、`F8` 前、`F9` 正、`FA` 在；重用前批相同 authored tiles
  `D8` 通、`D9` 訊、`F2` 中、`F3` 請、`F4` 稍、`F5` 候

## 重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_5.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-5.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-5.gba \
  --receipt /private/tmp/dqmch-message-batch-5.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_5.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-5.gba \
  --report /private/tmp/dqmch-message-batch-5-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-5.gba \
  /private/tmp/dqmch-message-batch-5.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-5.bps \
  /private/tmp/dqmch-message-batch-5-applied.gba

cmp /private/tmp/dqmch-message-batch-5.gba /private/tmp/dqmch-message-batch-5-applied.gba
```

## 結果

- verifier：`bounded_reextract=ok`、`allowed_range_count=11`、`changed_byte_count=352`、
  `outside_range_changes=0`、`runtime_qa=not-run`
- patched ROM SHA-256：`4683ED78D600D27368CE0A3AD0DA82EAD87974089543281FCE4F8F0AE263AD8C`
- target CRC32：`F31E608A`
- BPS：400 bytes、patch CRC32 `544957B8`、SHA-256
  `1328C1630DED9E556BFB289E91B78B3C9F6D892C15E4E7461FEB71069F0761A8`
- BPS apply 後 `cmp`：`ok`

這仍是固定 span／手繪字形的靜態 proof；尚未證明完整 encoder、字寬／VWF、
全量 ledger 或 mGBA runtime 畫面 QA。

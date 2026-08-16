# bounded message-batch-8 回插與 BPS receipt（2026-08-17）

這是 clean A9HJ `g06:v00:m0042`／`m0043` 的第八個有限批次，覆蓋相鄰的戰鬥拒絕訊息。
source-bearing work copy、patched ROM、BPS 與 JSON receipt 均留在 ignored `work/`、`roms/`
或 `/private/tmp`；本 receipt 不保存完整日文原文。

## 固定輸入與 encoder boundary

- clean ROM：CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- source-free ledger：`translations/message-batch-8.jsonl`
- `m0042` source hash：`BBFC4F6A5BC385CBB04598B9B3337A1598207A017E015C1F97CCDB8B56527719`
- `m0043` source hash：`F7319C4FCB2304CA7FF5DFBC72446D8AD7859D216D86CD6A262A529FCEAA5452`
- fixed spans：`m0042=0x286773..0x286781`（15 bytes）、`m0043=0x286782..0x286791`（16 bytes）；兩列最後的 `FF` 均保留
- targets：`m0042=已拒絕對戰。`、`m0043=對方拒絕對戰。`
- 新增 alternate glyph：E1/FF=`方`、E0/22=`拒`、E0/F7=`絕`
- 重用 authored glyph：E1/E7=`已`、E1/DA=`對`、E1/DB=`戰`
- mixed-bank encoder 使用已證明的 E0／E1 one-byte look-ahead；direct full-stop 為 clean `0x94`

## 可重現命令

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_8.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-8.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-8.gba \
  --receipt /private/tmp/dqmch-message-batch-8.json

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_8.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-8.gba \
  --report /private/tmp/dqmch-message-batch-8-verify.json

/usr/bin/ruby core/patches/bps_create.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-8.gba \
  /private/tmp/dqmch-message-batch-8.bps

/usr/bin/ruby core/patches/bps_apply.rb \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-8.bps \
  /private/tmp/dqmch-message-batch-8-applied.gba

cmp /private/tmp/dqmch-message-batch-8.gba /private/tmp/dqmch-message-batch-8-applied.gba
```

## 結果

verifier 得到 `bounded_reextract=ok`、`allowed_range_count=8`、`changed_byte_count=221`、
`outside_range_changes=0`。standalone patched ROM SHA-256 為
`036EFBADFF1BD5AF6F9C24E7514965D3673E6BD922CE0A9DD9081183E6F7647F`、CRC32 `C75F6519`；
BPS 為 276 bytes、CRC32 `2144DF1C`、SHA-256
`4F0567931B10B634E68EA3EAA07C39880619434CF0065C67FC0D7D6BC8C1962B`，apply 後 `cmp` 一致。

這筆 batch 只證明兩個固定 span 的 mixed-bank byte round-trip 與 BPS apply；`FF` 的完整遊戲語義、
全量 encoder、VWF／換行與 mGBA runtime QA 仍未完成。

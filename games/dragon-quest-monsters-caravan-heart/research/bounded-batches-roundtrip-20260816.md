# 六個 bounded batch 的 cumulative round-trip（2026-08-16）

`tools/build_bounded_batches.py` 將 `menu-batch-1`、`message-batch-2`、`message-batch-3`
與 `message-batch-4`、`message-batch-5`、`message-batch-6`
各自從同一份 clean A9HJ 產生，再以 byte-level merge 合併；若任兩批改到同一 byte 且內容
不同，工具會拒絕。
這是固定範圍的 cumulative proof，不是全遊戲 encoder。

可重現命令：

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/build_bounded_batches.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/menu-batch-1.jsonl \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-2.jsonl \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-3.jsonl \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-4.jsonl \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-5.jsonl \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-6.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-bounded-batches.gba \
  --report /private/tmp/dqmch-bounded-batches.json
```

執行時直接讀取六個 source-free ledger file；結果應保留六個 target、所有其他 ROM bytes 不變，且 `runtime_qa=not-run`。完整 script boundary、全字庫、全量
ledger、全遊戲 BPS 與 mGBA QA 仍是未完成 gate。

實際結果：六批合併 patched ROM SHA-256 為
`A170A3E5EF1505BB5196A20A1C30563D9577A15066079FFD954D5316D0602C48`；六個 bounded
target 都 `reextract=ok`，`allowed_range_count=52`、`changed_byte_count=1325`、
`outside_range_changes=0`。累積 BPS source CRC32 `3C24ABCC`、target CRC32 `E2ACF6E1`、
patch CRC32 `C2F6488B`、patch size 1401 bytes、BPS SHA-256
`AAC4E84D7EE89BEF66EE40BCEFBC73C9F2C34A65DBDAD010763A6EE0D66A1800`；apply 後與 cumulative
patched ROM `cmp` 一致。

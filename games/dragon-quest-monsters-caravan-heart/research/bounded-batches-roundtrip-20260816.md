# 三個 bounded batch 的 cumulative round-trip（2026-08-16）

`tools/build_bounded_batches.py` 將 `menu-batch-1`、`message-batch-2` 與 `message-batch-3`
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
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-bounded-batches.gba \
  --report /private/tmp/dqmch-bounded-batches.json
```

執行時直接讀取三個 source-free ledger file；結果應保留三個 target、所有其他 ROM bytes 不變，且 `runtime_qa=not-run`。完整 script boundary、全字庫、全量
ledger、全遊戲 BPS 與 mGBA QA 仍是未完成 gate。

實際結果：三批合併 patched ROM SHA-256 為
`6D4DC86922479CE283648782E9FD3A6CDFDFCDB401205836C5927DDCC5E150A6E`；三個 bounded
target 都 `reextract=ok`，`allowed_range_count=32`、`changed_byte_count=1041`、
`outside_range_changes=0`。累積 BPS source CRC32 `3C24ABCC`、target CRC32 `5AC8A15B`、
patch CRC32 `D18B0BC0`、patch size 1104 bytes、BPS SHA-256
`36134E1D9DA9AE4878C61836D1720299C469E6E731AAF26A1548C9968D92C005`；apply 後與 cumulative
patched ROM `cmp` 一致。

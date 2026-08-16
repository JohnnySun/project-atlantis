# `g06:v00:m0001` bounded round-trip（2026-08-16）

這是 clean A9HJ 的第二個 fixed-span 系統訊息 proof。它不代表全遊戲文字已完成。

- string id：`dqmch:a9hj:g06:v00:m0001`
- clean pointer／file span：`0x082864AA`／`0x2864AA..0x2864C4`，26 bytes
- original span SHA-256：`668377b360a03a4694aa1667bae75f908a9ad57656b2df205ab5ea70456ccf63`
- source-row SHA-256：`5a64df03ba085fe406d3f74781cead855443b5612cc9a726c5d0a0d6622f327f`
- zh-TW target：`冒險之書已消失。`
- fixed prefix budget：21 bytes；target 使用 8 個新 hand-authored E1 glyph slots，餘位填入 clean space code `BF`
- preserved tail：`FE E4 23 FB FF`，未改寫、未命名 `E4` 的 context-dependent parameter semantics
- new E1 slots：`E0 E3 E5 E6 E7 E8 E9 EA`

## 可重現檢查

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/patch_message_batch_2.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/translations/message-batch-2.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-message-batch-2.gba \
  --receipt /private/tmp/dqmch-message-batch-2.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_message_batch_2.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  /private/tmp/dqmch-message-batch-2.gba \
  --report /private/tmp/dqmch-message-batch-2-verify.json
```

預期的 verifier 邊界是：只允許 message span 與 8 個 alternate-bank tile ranges；所有其他
ROM bytes 必須保持一致；bounded re-extraction 應回復 target；`runtime_qa=not-run` 仍是明確
未完成項。

本輪實際結果：patched ROM SHA-256 為
`F06CABD745188738EBF1920F7D157E72FD75400643EDD5897CAE4AE03C2DAADD`；verifier
`changed_byte_count=277`、`allowed_range_count=9`、`outside_range_changes=0`、
`bounded_reextract=ok`。BPS 建立／套用也已完成：source CRC32 `3C24ABCC`、target CRC32
`7B169D6E`、patch CRC32 `ABFEF236`、patch size 321 bytes、BPS SHA-256
`BD1B13B83A8CD784173C6584CAD8216B302D7D96409FDDC3B52A9FB5DFAD9162`；套用結果與 patched
ROM `cmp` 完全一致。這仍是 bounded BPS proof，不是全遊戲 BPS gate。

這批次的 ledger 不含 `source`；完整 source 只存在 ignored `work/message-batch-2.jsonl`／
本機 decoded table。這個 batch 需要與第一批一起重新產生完整 BPS 才能進入發布 gate。

# clean token-preserving encoder round-trip（2026-08-17）

這份 receipt 將原本的 raw-span identity replay 升級為 extractor token stream 的 byte
re-encoding：`pair`、`alt-glyph`、`single-byte-candidate`、`control-candidate` 與截短
token 逐一重建 bytes，之後才寫回 pointer span 並驗證 clean ROM hash。它證明的是
token-preserving byte encoder，不是控制碼語義、script record boundary、完整 glyph identity、
字寬／VWF 或可直接供翻譯使用的 semantic encoder。

## 可重現命令

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/verify_raw_span_identity.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --report /private/tmp/dqmch-token-encoder-roundtrip.json
```

## clean A9HJ 結果

- ROM identity：size `8,388,608`、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- `record_count=37600`、`unique_pointer_count=4879`
- `token_record_count=37600`
- `token_reencode_bytes=1789312`（所有 pointer row span visits；其中 unique covered bytes 為 `214948`）
- `token_reencode_mismatches=0`
- raw span mismatch：`0`
- clean 與 token-reencoded rebuild SHA-256 相同：
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- `changed_byte_count=0`
- `token_encoder=proven`
- `semantic_encoder=not-proven; token-preserving only`
- `runtime_qa=not-run`

`FF`、其他 `DF..FF` bytes 與 unknown glyph 仍只以 token 形式保留；這個結果不替它們命名，
也不把下一個 pointer 候選提升為已證明的 record boundary。

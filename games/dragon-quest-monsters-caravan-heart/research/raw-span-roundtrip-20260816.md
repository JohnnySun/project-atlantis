# clean raw-span identity round-trip（2026-08-16）

這份 receipt 只關閉「extractor 輸出的每筆 raw span 與 clean ROM 相符，原 bytes 重放後 ROM
不變」的狹義 gate。它不代表已證明 script record boundary、控制碼語義、完整 glyph identity、
字寬／VWF 或可翻譯的 semantic encoder；那些 roadmap gate 仍保持開放。

## 可重現命令

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/verify_raw_span_identity.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --report /private/tmp/dqmch-raw-span-identity.json
```

## clean A9HJ 結果

- ROM identity：size `8,388,608`、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- `record_count=37600`、`unique_pointer_count=4879`
- 每筆 `pointer_file..span_end_file` 的 raw slice 都 exact：`raw_span_mismatches=0`
- 唯一涵蓋 bytes：`covered_byte_count=214948`；重疊 span byte visits：`overlap_byte_count=1574364`
- deterministic raw span digest：`4454038E5241AA8C7B02EA29CBBE729A82AA990A86662B4079066B41C77BD091`
- clean 與 raw replay rebuild SHA-256 相同：
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- `changed_byte_count=0`、`semantic_encoder=not-proven`、`runtime_qa=not-run`

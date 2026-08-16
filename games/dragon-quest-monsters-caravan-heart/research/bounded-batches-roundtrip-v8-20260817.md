# 八個 bounded batch 的 cumulative round-trip（2026-08-17）

`tools/build_bounded_batches.py` 從同一份 clean A9HJ 分別重建 menu batch、message batch 2–8，
再以 byte-level merge 合併；任兩批改到同一 byte 且內容不同時工具會拒絕。這是固定範圍的
cumulative proof，不是全遊戲 encoder。

執行時讀取八個 source-free ledger file 與被忽略的 clean source table／raw-token table，
結果應保留九個 target rows，且所有其他 ROM bytes 不變。實際報告：

- cumulative patched ROM SHA-256：`A91ED852A59CEAF0C036E2721F0A8A10172097E17A340A993863692A82A414B7`
- target CRC32：`AE8207A2`
- `allowed_range_count=67`
- `changed_byte_count=1528`
- `outside_range_changes=0`
- 九個 bounded rows 的 re-extraction：全部 `ok`
- cumulative BPS：1623 bytes、CRC32 `2144DF1C`、SHA-256
  `7E6FC9E210B6B8E5BF9A65D02E62C631294604DAEC3F9F491CAFA02EF877F2D0`
- BPS apply 後與 cumulative patched ROM `cmp` 一致

`runtime_qa=not-run`。完整 script boundary、全字庫、全量 ledger、全遊戲 BPS 與 mGBA 場景 QA
仍是未完成 gate。

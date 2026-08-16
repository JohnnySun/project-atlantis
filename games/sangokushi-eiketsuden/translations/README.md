# 翻譯資料邊界

本遊戲的四組 bounded pointer pool 已有遊戲專用 decoder；原文表仍只在本機產生。第一個
翻譯批次限定於已核對結構、可由現有 codepage glyph 覆蓋的 Table B battle-effect
records，並以 source hash 綁定。已提交的 `table-b-batch-1.jsonl` 只有 B0–B5 六筆
不含 `source` 的 ledger；它是固定槽位 encoder 的第一個靜態安全批次，不代表整部遊戲
或自然畫面 reachability 已完成。未進入批次的 pool A/C/D 不猜測 string ID 或畫面語意。

預定流程：

```text
本機 ROM decoder（`tools/extract_text_pools.py`）
  -> research/sangokushi-eiketsuden-decoded.jsonl  （忽略、不提交）
  -> core/ledger/restore_translations.rb
  -> work/*.jsonl                                    （忽略、不提交）
  -> core/ledger/strip_translations.rb
  -> translations/*.jsonl                            （只提交不含 source 的 ledger）
```

目前的翻譯相關檔案包括 [`glossary.zh-TW.tsv`](glossary.zh-TW.tsv) 和
[`table-b-batch-1.jsonl`](table-b-batch-1.jsonl)。前者保存公開資料研究得到的術語候選；
後者保存 B0–B5 的 `zh-TW`／schema 目標、source hash、上下文與 `ai_review` 狀態，
不含 ROM 原文。完整翻譯、術語審核、自然 runtime QA 和其他 pool 仍未完成。

## 第一批的可重現邊界

`restore_translations.rb` 只在本機把 ignored decoded source table 合併成 `work/*.jsonl`；
`strip_translations.rb` 再產生可提交 ledger。B0–B5 的 restore→strip 輸出與 tracked
ledger 已逐 byte 相同，6 筆均沒有 `source` 欄位。`tools/font_coverage.py` 顯示六筆
目標的 strict Shift-JIS、1834-entry codepage 與兩組 0x20-byte glyph slot 全部覆蓋，且
均未超過各自原始固定槽位。

`tools/patch_table_b.py` 和 `tools/verify_table_b_patch.py` 目前只允許 Table B 的
固定槽位、禁止 relocation；B0–B5 共 6 個 record 改變 42 bytes，44-entry pointer table
保持不變，6/6 重新抽取相符，未選取 record 維持 byte-identical。這是 bounded insertion
receipt，不是全遊戲 encoder 或發布 patch 的完成證明；BPS 與 mGBA 結果見
[`research/m3-batch1-roundtrip-20260816.md`](../research/m3-batch1-roundtrip-20260816.md)。

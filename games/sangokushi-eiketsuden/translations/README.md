# 翻譯資料邊界

本遊戲的四組預設 bounded pointer pool 已有遊戲專用 decoder；另有獨立的 story-event E
（`0x0CDB64/33`）static analyzer，只有 `extract_text_pools.py --include-story` 才會在本機
額外產生它的 source table。原文表仍只在本機產生。第一個
翻譯批次限定於已核對結構、可由現有 codepage glyph 覆蓋的 Table B battle-effect
records，並以 source hash 綁定。已提交的 `table-b-batch-1.jsonl` 有 B0–B5 六筆，
`table-b-batch-2.jsonl` 再增加 19 筆 unique records；兩者都是固定槽位 encoder 的
靜態安全批次，不代表整部遊戲
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

目前的翻譯相關檔案包括 [`glossary.zh-TW.tsv`](glossary.zh-TW.tsv)、
[`table-b-batch-1.jsonl`](table-b-batch-1.jsonl)、
[`table-b-batch-2.jsonl`](table-b-batch-2.jsonl)、
[`table-b-batch-3.jsonl`](table-b-batch-3.jsonl)、
[`event-system-batch-1.jsonl`](event-system-batch-1.jsonl) 和
[`event-system-batch-2.jsonl`](event-system-batch-2.jsonl)、
[`system-item-class-batch-1.jsonl`](system-item-class-batch-1.jsonl) 和
[`system-item-class-batch-2.jsonl`](system-item-class-batch-2.jsonl) 和
[`system-item-class-batch-3.jsonl`](system-item-class-batch-3.jsonl) 和
[`system-item-class-batch-4.jsonl`](system-item-class-batch-4.jsonl) 和
[`system-item-class-batch-5.jsonl`](system-item-class-batch-5.jsonl)、
[`story-event-batch-1.jsonl`](story-event-batch-1.jsonl) 和
[`story-event-batch-2.jsonl`](story-event-batch-2.jsonl) 和
[`story-event-batch-3.jsonl`](story-event-batch-3.jsonl) 和
[`story-event-batch-4.jsonl`](story-event-batch-4.jsonl) 和
[`story-event-batch-5.jsonl`](story-event-batch-5.jsonl) 和
[`story-event-batch-6.jsonl`](story-event-batch-6.jsonl) 和
[`story-event-batch-7.jsonl`](story-event-batch-7.jsonl) 和
[`story-event-batch-8.jsonl`](story-event-batch-8.jsonl) 和
[`story-event-batch-9.jsonl`](story-event-batch-9.jsonl) 和
[`story-event-batch-10.jsonl`](story-event-batch-10.jsonl) 和
[`story-event-batch-11.jsonl`](story-event-batch-11.jsonl) 和
[`story-event-batch-12.jsonl`](story-event-batch-12.jsonl) 和
[`story-event-batch-13.jsonl`](story-event-batch-13.jsonl) 和
[`story-event-batch-14.jsonl`](story-event-batch-14.jsonl) 和
[`story-event-batch-15.jsonl`](story-event-batch-15.jsonl) 和
[`story-event-batch-16.jsonl`](story-event-batch-16.jsonl) 和
[`story-event-batch-17.jsonl`](story-event-batch-17.jsonl) 和
[`story-event-batch-18.jsonl`](story-event-batch-18.jsonl)。前者保存公開資料研究得到的
術語候選；二十八個 ledger 保存 Table B／event-system／system-item-class／story-event E 的 `zh-TW`／schema
目標、source hash、上下文與 `ai_review` 狀態，不含 ROM 原文。Table B 的 26 個 unique
records 已有 ledger；pool A 先建立 34 筆 bounded rows，story-event E batch 1／2 先建立
E:002／E:011／E:032 的 existing-codepage rows。E source 使用的 raw code units 與既有
custom map 重疊，所以 E batch 1／2 維持 E-specific guard；batch 3–6／8／9／10／11／12／13／14／15／17 另以完整 292-record
source-use cohort 建立十二個 custom glyph slots，不能直接沿用四池 custom-glyph patch。
E 目前共 33 個 source-free rows，33/33 unique records 已有 record-level ledger；公開攻略只提供
`provisional-known-screen-cross`，自然 runtime QA 和人工終審仍未完成。

## 第一批的可重現邊界

`restore_translations.rb` 只在本機把 ignored decoded source table 合併成 `work/*.jsonl`；
`strip_translations.rb` 再產生可提交 ledger。目前二十八批的 restore→strip 輸出均與 tracked
ledger 逐 byte 相同，合計 108 筆均沒有 `source` 欄位；existing-codepage rows
由 `font_coverage.py` 驗證，其餘 custom-glyph／custom-aware rows 由
`custom_glyph_patch.py`／`verify_custom_glyph_patch.py` 驗證，均未超過各自原始固定槽位。

`tools/patch_table_b.py`／`tools/verify_table_b_patch.py` 和
`tools/patch_fixed_pool.py`／`tools/verify_fixed_pool_patch.py` 目前只允許 reviewed
pool 的固定槽位、禁止 relocation；Table B batch 1／2 共 25 個 unique records 改變 280
bytes，event-system batch 1 再有 9 個 unique records 改變 34 bytes；Table B batch 3
另改變 120 bytes，event-system batch 2 改變 360 bytes。各批 pointer table 都保持不變，
existing rows 分別 6/6、19/19、9/9；custom rows 分別 1/1、12/12、5/5、6/6、12/12、31/31 重新抽取相符，
未選取 record 維持 byte-identical；system-item-class pool A 的 pointer table 也保持不變；
story-event E batch 3 的 E-specific custom patch 改變 `321` bytes、custom plane `3/3`，
E pointer／codepage tables 也保持不變。
這是 bounded insertion receipt，不是全遊戲 encoder 或發布 patch 的完成證明；BPS 與
mGBA 結果見
[`research/m3-batch1-roundtrip-20260816.md`](../research/m3-batch1-roundtrip-20260816.md)
、[`research/m3-batch2-roundtrip-20260816.md`](../research/m3-batch2-roundtrip-20260816.md)
、[`research/m3-event-system-batch1-roundtrip-20260816.md`](../research/m3-event-system-batch1-roundtrip-20260816.md)、
[`research/m3-batch3-roundtrip-20260816.md`](../research/m3-batch3-roundtrip-20260816.md)、
[`research/m3-event-system-batch2-roundtrip-20260816.md`](../research/m3-event-system-batch2-roundtrip-20260816.md)、
[`research/m3-system-item-class-batch4-roundtrip-20260816.md`](../research/m3-system-item-class-batch4-roundtrip-20260816.md)
、[`research/m3-system-item-class-batch5-roundtrip-20260816.md`](../research/m3-system-item-class-batch5-roundtrip-20260816.md)
及 [`research/m3-custom-glyph-format-20260816.md`](../research/m3-custom-glyph-format-20260816.md)。
story-event E batch 1 的 E:002／E:011 另見
[`research/m3-story-event-batch1-roundtrip-20260816.md`](../research/m3-story-event-batch1-roundtrip-20260816.md)。
story-event E batch 2 的 E:032 另見
[`research/m3-story-event-batch2-roundtrip-20260816.md`](../research/m3-story-event-batch2-roundtrip-20260816.md)。
story-event E batch 3 的 E:003／E:004 另見
[`research/m3-story-event-batch3-roundtrip-20260816.md`](../research/m3-story-event-batch3-roundtrip-20260816.md)；
公開結局流程交叉證據見
[`research/m3-story-known-screen-cross-20260816.md`](../research/m3-story-known-screen-cross-20260816.md)。
story-event E batch 4 的 E:005 另見
[`research/m3-story-event-batch4-roundtrip-20260816.md`](../research/m3-story-event-batch4-roundtrip-20260816.md)。
story-event E batch 5 的 E:006 另見
[`research/m3-story-event-batch5-roundtrip-20260816.md`](../research/m3-story-event-batch5-roundtrip-20260816.md)。
story-event E batch 6 的 E:007／E:008 另見
[`research/m3-story-event-batch6-roundtrip-20260816.md`](../research/m3-story-event-batch6-roundtrip-20260816.md)。
story-event E batch 7 的 E:009／E:010 另見
[`research/m3-story-event-batch7-roundtrip-20260816.md`](../research/m3-story-event-batch7-roundtrip-20260816.md)。
story-event E batch 8 的 E:012／E:013 另見
[`research/m3-story-event-batch8-roundtrip-20260816.md`](../research/m3-story-event-batch8-roundtrip-20260816.md)。
story-event E batch 9 的 E:014／E:015 另見
[`research/m3-story-event-batch9-roundtrip-20260816.md`](../research/m3-story-event-batch9-roundtrip-20260816.md)。
story-event E batch 10 的 E:016／E:017 另見
[`research/m3-story-event-batch10-roundtrip-20260816.md`](../research/m3-story-event-batch10-roundtrip-20260816.md)。
story-event E batch 11 的 E:018／E:019 另見
[`research/m3-story-event-batch11-roundtrip-20260816.md`](../research/m3-story-event-batch11-roundtrip-20260816.md)。
story-event E batch 12 的 E:020／E:021 另見
[`research/m3-story-event-batch12-roundtrip-20260816.md`](../research/m3-story-event-batch12-roundtrip-20260816.md)。
story-event E batch 13 的 E:022／E:023 另見
[`research/m3-story-event-batch13-roundtrip-20260816.md`](../research/m3-story-event-batch13-roundtrip-20260816.md)。
story-event E batch 14 的 E:024／E:025 另見
[`research/m3-story-event-batch14-roundtrip-20260816.md`](../research/m3-story-event-batch14-roundtrip-20260816.md)。
story-event E batch 15 的 E:026／E:027 另見
[`research/m3-story-event-batch15-roundtrip-20260816.md`](../research/m3-story-event-batch15-roundtrip-20260816.md)。
story-event E batch 16 的 E:028／E:029 另見
[`research/m3-story-event-batch16-roundtrip-20260816.md`](../research/m3-story-event-batch16-roundtrip-20260816.md)。
story-event E batch 17 的 E:030／E:031 另見
[`research/m3-story-event-batch17-roundtrip-20260816.md`](../research/m3-story-event-batch17-roundtrip-20260816.md)。
story-event E batch 18 的 E:000／E:001 另見
[`research/m3-story-event-batch18-roundtrip-20260816.md`](../research/m3-story-event-batch18-roundtrip-20260816.md)。

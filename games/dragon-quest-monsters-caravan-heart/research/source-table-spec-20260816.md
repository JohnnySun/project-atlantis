# A9HJ 本機 source table 規格（2026-08-16）

這份文件只定義可重跑的本機中間層，不是已完成的日文原文解碼或翻譯來源。真正的
`research/*-decoded.jsonl` 含有 ROM 原文，只能由持有合法 clean A9HJ ROM 的研究者在
本機產生，不能提交。

## row contract

`tools/build_source_table.py` 由 `tools/extract_text.py` 的 token JSONL 產生每行：

```json
{"string_id":"dqmch:a9hj:g06:v00:m0000","locale":"ja-JP","text":"<local-only>","provenance":"<hash;pointer;boundary;decoder>"}
```

`string_id` 由三層 pointer table 的 group／variant／message index 產生，不使用抽取順序。
`provenance` 固定記錄 clean ROM SHA-256、CPU/file offset、候選 span boundary、decoder
版本與 `runtime_context=false`。source text 只能留在 ignored `research/` 或 `/private/tmp`。

目前可安全顯示的 glyph identity 僅限 clean atlas 已交叉核對的 ASCII、平假名區域、由
atlas／名稱 context 交叉確認的 `0x59=を`、`0x5A=ん`、`0x90=ヲ`、`0x5B..0x8F` 的 katakana 順序、
`0x91=ン`、公開 code table 與 clean atlas 共同核對的 `0x94..0xBD` direct punctuation／UI
units（`0xB8` 除外），以及空白 glyph。`0x92`／`0x93` 只有在 trail 對應已知可濁音／半濁音
假名 base 時，才依 clean pair writer 與多筆名稱／menu context 解出；其他 pair 仍輸出
`{Uxxxx}`。其餘 `<0xDF` 單位輸出 `{Uxx}`，`0xDF..0xFF` 控制候選輸出大寫 `{HH}`。
這種 placeholder 是刻意的 drift／誤翻譯防線，不是猜測的 Unicode mapping；glyph table
後段仍未命名。

`0xE0`／`0xE1` 不視為單一 glyph 或可直接丟棄的 marker：clean handler 已證明它們會各自
消費下一 byte，並由 `0x08013E4C` 送入 alternate glyph pool `0x082E0BD4`；handler 以 lead
選擇 bank：`E0` 使用 base，`E1` 使 state bit 1 加上 `0x4000` byte bias 取第二 bank。目前
renderer 已把兩條 one-byte alt-glyph 路徑分別視覺化，
尚未把 alt pool index 命名成 Unicode；因此 source table 仍保留 control／alt glyph 的
provenance gate，不能把 OCR 候選直接升成 ledger source。

## ledger gate

本輪 extractor 的 pointer pool 混有文字、資料與狀態 records；`next-pointer` 只是一個
候選 span，不能單獨視為字串終點。即使 row 含 `{FF}`，也必須另外具備：

1. terminator／jump／bank／控制參數的 parser 證據；
2. code unit 到 glyph identity 的完整覆蓋，沒有 `{Uxx}`／`{Uxxxx}`；
3. 可重現的 title／menu／事件語境與 runtime consumer 交叉證據；
4. encoder 能把同一 source row 回寫並重新抽取，且未修改內容保持一致。

因此 `build_source_table.py` 的目前所有 rows 都標成 `ledger_eligible=false`，即使 local
source text 已可供研究者檢視，也不能直接交給 `restore_translations.rb` 或建立
`translations/*.jsonl`。只有達成上述 gate 後，才可建立 `work/*.jsonl`、填入已查核的
`zh-TW`／`zh-Hans`，再用 `strip_translations.rb` 產生不含 `source` 的 ledger。

## 未命名 direct units 的上下文盤點

`tools/audit_codepage_inventory.py` 的 v2 receipt 另按 `group`／`variant` 聚合未命名
direct units，不輸出 pointer、raw bytes 或文字。clean run 中 `0xB8`／`0xBE`／`0xC0..0xDE`
並非只在單一事件字串出現，而是在多個 variant 重複出現相同的 unit 集合與固定計數形狀；
`g00`、`g01`、`g02`、`g03`、`g07` 的重複池尤其明顯。這是 pointer pool／資料樣本的
結構性訊號，不是 glyph identity 或語義的證明，因此這些 units 仍留在 `{Uxx}`，不得因
頻率或 code table 相鄰性升格成可翻譯字元。完整 source-free 聚合可由上述命令重建，並與
本文件的 clean hash 一起審核。

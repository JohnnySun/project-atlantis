# 翻譯資料邊界

本遊戲尚未建立翻譯批次。日版 ROM 到位並完成遊戲專用 decoder 前，不建立含 `source` 的工作記錄，也不猜測 `string_id`。

預定流程：

```text
本機 ROM decoder
  -> research/sangokushi-eiketsuden-decoded.jsonl  （忽略、不提交）
  -> core/ledger/restore_translations.rb
  -> work/*.jsonl                                    （忽略、不提交）
  -> core/ledger/strip_translations.rb
  -> translations/*.jsonl                            （只提交不含 source 的 ledger）
```

目前唯一的翻譯相關檔案是 [`glossary.zh-TW.tsv`](glossary.zh-TW.tsv)，它保存公開資料研究得到的術語候選，不含 ROM 原文，也不代表任何字串已通過 QA。

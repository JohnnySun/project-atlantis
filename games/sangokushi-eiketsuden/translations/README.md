# 翻譯資料邊界

本遊戲的四組 bounded pointer pool 已有遊戲專用 decoder；原文表仍只在本機產生。第一個
翻譯批次會先限定於已核對結構、可由現有 codepage glyph 覆蓋的 Table B battle-effect
records，並以 source hash 綁定；未進入批次的 pool A/C/D 不猜測 string ID 或畫面語意。

預定流程：

```text
本機 ROM decoder（`tools/extract_text_pools.py`）
  -> research/sangokushi-eiketsuden-decoded.jsonl  （忽略、不提交）
  -> core/ledger/restore_translations.rb
  -> work/*.jsonl                                    （忽略、不提交）
  -> core/ledger/strip_translations.rb
  -> translations/*.jsonl                            （只提交不含 source 的 ledger）
```

目前唯一的翻譯相關檔案是 [`glossary.zh-TW.tsv`](glossary.zh-TW.tsv)，它保存公開資料研究得到的術語候選，不含 ROM 原文，也不代表任何字串已通過 QA。

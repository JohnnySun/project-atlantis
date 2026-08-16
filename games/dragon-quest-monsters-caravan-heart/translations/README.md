# 翻譯資料邊界

本遊戲採用 Project Atlantis 的 source／work／ledger 分離流程：

```text
clean A9HJ + tools/extract_text.py + tools/build_source_table.py
  -> research/dragon-quest-monsters-caravan-heart-decoded.jsonl  # 本機原文，忽略
  -> core/ledger/restore_translations.rb
  -> work/*.jsonl                                                # 本機工作記錄，忽略
  -> core/ledger/strip_translations.rb
  -> translations/*.jsonl                                        # 唯一可提交形式，禁止 source
```

截至 2026-08-16，尚未建立可提交 ledger。clean consumer、glyph table、mixed-byte pair
path、`E0`／`E1` alternate glyph path 與穩定 menu 已有證據，但完整 codepage、控制碼／
終止／跳躍、字寬／VWF、script record boundary 與 encoder round-trip 尚未完成。source
table 產生器因此只提供保守的本機候選：未知 direct glyph 會變成 `{Uxx}`／`{Uxxxx}`，未命名
alternate glyph 會變成 `{G` + 兩位 lead + 兩位索引 + `}`（例如 `{GE08D}`），控制候選會變成 `{HH}`，所有 rows 固定
`ledger_eligible=false`。目前 clean v4 provisional receipt 為 37,600 rows、103,209 個
pair tokens、39,225 個 alternate-glyph tokens、217,774 個 control candidates；這些數字是
研究聚合，不是可提交翻譯覆蓋率。

在 M1 gate 通過前，不從英文 patch 或其他中文 patch 反推日文原文，也不把猜測的專有
名詞或翻譯寫入 `translations/`。進入第一批翻譯時，必須先建立
`glossary.zh-TW.tsv`，並依 `AGENTS.md` 以 Wikipedia zh-tw、巴哈姆特及其他獨立社群
來源核對勇者鬥惡龍專有名詞。

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

截至 2026-08-16，已建立四筆 source-free bounded ledger；clean consumer、glyph table、mixed-byte pair
path、`E0`／`E1` alternate glyph path 與穩定 menu 已有證據，但完整 codepage、控制碼／
終止／跳躍、字寬／VWF、script record boundary 與 encoder round-trip 尚未完成。source
table 產生器因此只提供保守的本機候選：未知 direct glyph 會變成 `{Uxx}`／`{Uxxxx}`，未命名
alternate glyph 會變成 `{G` + 兩位 lead + 兩位索引 + `}`（例如 `{GE08D}`），控制候選會變成 `{HH}`，所有 rows 固定
`ledger_eligible=false`。目前 clean v5 provisional receipt 為 37,600 rows、103,209 個
pair tokens、39,225 個 alternate-glyph tokens、217,774 個 control candidates；這些數字是
研究聚合，不是可提交翻譯覆蓋率。

`menu-batch-1.jsonl` 只覆蓋 clean `g06:v00:m0000` 的 title-menu block。其 encoder 使用
14 個手繪 8x8 glyph，配置到 clean extractor 證明未使用的 E1 slots，保留兩個 `FF`；這是
固定 span／字庫 plumbing proof，不代表完整中文字庫或全遊戲 coverage。source-bearing
restore output 仍只寫入 ignored `work/`。

`message-batch-2.jsonl` 只覆蓋 clean `g06:v00:m0001` 的 save-loss system message。其 encoder
使用 8 個新手繪 E1 glyph，固定 span 尾端 `FE E4 23 FB FF` 完整保留；restore／strip／schema、
bounded re-extraction 與 BPS apply 均已重現，但兩批仍標成 `ai_review`，mGBA runtime QA 尚未跑。

`message-batch-3.jsonl` 只覆蓋 clean `g06:v00:m0006` 的 communication-status line。其 encoder
使用 7 個與前兩批不重疊的新手繪 E1 glyph，固定 span 最後的 `FF` 完整保留；restore／strip、
bounded re-extraction 與 BPS apply 均已重現，仍標成 `ai_review`，mGBA runtime QA 尚未跑。

`message-batch-4.jsonl` 只覆蓋 clean `g06:v00:m0044` 的 communication wait prompt。其 encoder
使用 3 個與前三批不重疊的新手繪 E1 glyph，採用 clean direct `0x94` full-stop，固定 span 最後的
`FF` 完整保留；restore／strip、bounded re-extraction 與 BPS apply 均已重現，仍標成
`ai_review`，mGBA runtime QA 尚未跑。

`tools/build_bounded_batches.py` 會從 clean ROM 分別重建四批並拒絕 range conflict；cumulative
ROM／BPS 只是一個目前可審核的有限 proof，不能替代全量 decoder、全字庫或完整 QA。

在 M1 gate 通過前，不從英文 patch 或其他中文 patch 反推日文原文，也不把猜測的專有
名詞或翻譯寫入 `translations/`。進入第一批翻譯時，必須先建立
`glossary.zh-TW.tsv`，並依 `AGENTS.md` 以 Wikipedia zh-tw、巴哈姆特及其他獨立社群
來源核對勇者鬥惡龍專有名詞。

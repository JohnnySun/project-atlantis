# B3CJ 可提交翻譯帳本

這個目錄只接受由本機工作檔產生的 ledger JSONL，不直接編輯帶有 `source.text` 的記錄。

```sh
ruby core/ledger/restore_translations.rb \
  games/summon-night-craft-sword-3/translations/BATCH.jsonl \
  games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  games/summon-night-craft-sword-3/work/BATCH.jsonl

ruby core/ledger/strip_translations.rb \
  games/summon-night-craft-sword-3/work/BATCH.jsonl \
  games/summon-night-craft-sword-3/translations/BATCH.jsonl
```

M2.5 的第一個實例是 `m2.5-prize-ui.jsonl`：先由
`tools/build_m2_5_batch.py prepare` 從 ignored source table 建立一筆 ignored
source adapter，再執行上面的 `restore → work → strip`。tracked ledger 固定
`source_hash`、`zh-TW`／`zh-Hans` target、`ai_draft` status、context、terms 與 review
metadata，不含 `source` 或 `source_text`；完整原文、source adapter 與工作檔不得提交。

`tools/validate_ledger.py` 會以固定 source-table hash、stable `string_id` 與 core
`restore_translations.rb`／`strip_translations.rb` 重跑這個契約；extractor 使用的
`source_text` 只在暫存 local adapter 中轉成 core 所需的 `text`，不會寫入 tracked
ledger。它也拒絕 source key、source hash drift、錯誤 game／revision、缺少 `zh-TW`
target 或未知 status。

M4.1 的 `m4.1-wood-chopping.jsonl` 延續同一規則；其 cumulative ROM build 依賴
ignored M2.5 working copy，但 tracked ledger 只保存新 record 的 source hash、target
metadata 與 review status。

M4.2 的 `m4.2-warning-label.jsonl` 也只保存一筆 resource-16 record 的 source hash、
target metadata 與 `ai_draft` status；其 cumulative builder 會在 ignored work 中先
重建 M2.5／M4.1，再做 existing-mapped-glyph 的同長度 resource-16 static build。

M4.3 的 `m4.3-ellipsis-label.jsonl` 只保存一筆 resource-25 record 的 source hash、
target metadata 與 `ai_draft` status；其 builder 先重建前面三筆 cumulative targets，
再以 `ec6d→0x84c` 的單一 allowed blank slot 做同長度 static build。

M5.2 的 `m5.2-reward-relocation.jsonl` 只保存一筆 resource-24 record 的 source hash、
target metadata 與 `ai_draft` status；其 builder 先重建 M2.5／M4.1／M4.2／M4.3，
再以既有 `ec65→0x848` 與新增 `ec6e→0x84d` 做 target build，並將 resource directory
重導到 M5.1 已驗證的 zero-filled destination。完整原文、source adapter、working copy、
relocated ROM 與 BPS 仍只在 ignored `research/*-decoded.jsonl`／`work/`。

這個目錄只保存已通過 schema／safety 的可提交 ledger；M2.5 的 target 仍需人工／術語、
字型與 runtime 審核，不能把 ledger 存在視為翻譯完成。`research/*-decoded.jsonl` 與
`work/` 已由 repository ignore 規則排除；若新檔名不符合既有規則，提交前必須用
`git check-ignore -v` 確認，也不把外部 patch 的腳本內容複製進來。

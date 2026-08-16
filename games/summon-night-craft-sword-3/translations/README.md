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

這個目錄只保存已通過 schema／safety 的可提交 ledger；M2.5 的 target 仍需人工／術語、
字型與 runtime 審核，不能把 ledger 存在視為翻譯完成。`research/*-decoded.jsonl` 與
`work/` 已由 repository ignore 規則排除；若新檔名不符合既有規則，提交前必須用
`git check-ignore -v` 確認，也不把外部 patch 的腳本內容複製進來。

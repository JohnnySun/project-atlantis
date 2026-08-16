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

`research/*-decoded.jsonl` 與 `work/` 已由 repository ignore 規則排除；若新檔名不符合既有規則，提交前必須用 `git check-ignore -v` 確認。未解出本作文本格式前，不建立翻譯批次，也不把外部 patch 的腳本內容複製進來。

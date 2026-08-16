# FE6 翻譯 ledger

本目錄只接受由 `core/ledger/strip_translations.rb` 從本機 `work/` 工作記錄產生的 ledger。任何提交記錄都不得含有 `source` 或日版原文。

目前尚未有翻譯批次：AFEJ ROM 身分與一條 runtime 字元消費路徑已確認，但完整文本解碼器、控制碼、字寬限制與回插仍未確認。請不要先建立猜測性的 `string_id` 或把既有英文 patch 當作原文來源。

標準流程：

```sh
ruby core/ledger/restore_translations.rb \
  games/fire-emblem-6-binding-blade/translations/BATCH.jsonl \
  games/fire-emblem-6-binding-blade/research/afej-decoded.jsonl \
  games/fire-emblem-6-binding-blade/work/BATCH.jsonl

ruby core/ledger/strip_translations.rb \
  games/fire-emblem-6-binding-blade/work/BATCH.jsonl \
  games/fire-emblem-6-binding-blade/translations/BATCH.jsonl
```

第一次批次可從本機原文表直接建立 `status: untranslated` 工作記錄；只把 strip 後的檔案提交。

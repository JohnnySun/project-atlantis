# M4 bounded target-side QA

`tools/audit_translation_batches.py` 對目前四筆 cumulative `ai_draft` ledger 做
target-side gate，不讀取或輸出日文 source。它檢查 stable ID、ledger／plan target
一致、UTF-8 hash、Shift-JIS／opaque extension code units、byte length、單行寬度、
`0x0308`／`0x0000` contract、allowed glyph allocation 範圍與唯一性、已知簡體字
漏入，以及 tracked ledger 沒有 `source`／`source_text`。source hash 與 core
restore→strip 仍由 `tools/validate_ledger.py` 另外驗證。

固定收據：4 個 bounded batches、4 個 unique string IDs、target code-unit counts
`7/6/5/4`、allocation counts `3/2/0/1`。目前所有 batch 仍是 `ai_draft`；這個
QA 只證明可重跑的 metadata／layout gate，不是人工翻譯審核、runtime screen QA 或
發布資格。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/audit_translation_batches.py \
  --summary-output games/summon-night-craft-sword-3/work/m4-target-qa-summary.json
```

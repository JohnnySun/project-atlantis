# M3：原文表與可逆 ledger workflow audit

本切片確認本作的 local extractor source table 可以安全接到共用 ledger
workflow；日文原文只從 ignored local table 讀取，研究文件不保存原文句子。

## 固定收據

- source table：361 筆 stable `string_id`，locale `ja-JP`，SHA-256
  `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3`。
- tracked ledger：`translations/m2.5-prize-ui.jsonl`，目前 1 筆
  `b3cj:t2:024:0x0064`，game／revision 固定為本作／`B3CJ`，target locale
  明確包含 `zh-TW`，status 是 `ai_draft`。
- `tools/validate_ledger.py` 先驗證 source hash、stable ID、ledger schema shape、
  target/status 與禁止 `source`／`source_text` 欄位，再在暫存目錄把 extractor
  的 `source_text` 轉成 core ledger 所需的 local `text` adapter，實際執行
  `restore_translations.rb` → `strip_translations.rb`。
- restore／strip 後的 ledger JSON values 完全一致；測試另證明嵌入 source key
  與 source-table drift 都會拒絕。暫存 adapter／working output 不在 repository
  內，沒有新增可提交原文。

## 重跑命令

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/summon-night-craft-sword-3/tools/validate_ledger.py \
  games/summon-night-craft-sword-3/translations/m2.5-prize-ui.jsonl \
  games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --require-id b3cj:t2:024:0x0064 \
  --summary-output games/summon-night-craft-sword-3/work/m3-ledger-summary.json
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/summon-night-craft-sword-3/tools/test_validate_ledger.py -v
```

這只證明 source／work／ledger 分界與第一筆 ledger 的可逆性，不代表該筆譯文已
人工審核、runtime 可達或可發布；下一個翻譯批次仍需逐筆通過 control、byte-length、
glyph allocation、resource capacity、source hash 與 re-extraction 契約。

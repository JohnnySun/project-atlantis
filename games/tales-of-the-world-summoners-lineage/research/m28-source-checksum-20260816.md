# A9PJ M28 source checksum／drift gate（2026-08-16）

M28 建立 source table 進入 ledger 前的 local-only audit：驗證 stable ID、decoder version、
provenance、UTF-8 `source_text_sha256`、runtime/context 欄位與 duplicate ID。它只輸出
counts、IDs、hash mismatch 與 gate，不輸出 source text；輸入和 receipt 都留 private／
ignored 路徑。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m28_source_checksum_probe.py \
  /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl \
  --output /private/tmp/tow-a9pj-m28-checksum/summary.json
```

本輪 M27 local receipt 預期為 46 rows，source hash 與 schema 均可驗證；但所有 rows
仍 `runtime_context=false`、`scene_role=unclassified`、`eligible_for_ledger=false`，所以
M28 `ledger_gate.open=false`。這證明 checksum implementation 可運作，不宣稱已建立
可提交 source table 或翻譯 batch。

## gate 規則

- hash mismatch、缺欄位或 duplicate `string_id` 立即關閉 gate。
- hash 正確不等於 codepage／控制碼／scene role 正確；provisional decoder 不能開 gate。
- 只有 runtime/context 已確認、source rows 使用穩定 decoder version，且翻譯記錄通過
  `strip_translations.rb` 後，才允許進入下一個 minimal ledger／round-trip slice。

## 下一個最小缺口

取得一個真正 runtime-backed、無 unresolved／control ambiguity 的短 UI row；以 M28 產生
source checksum，再接 `restore_translations.rb`／`strip_translations.rb` 的 synthetic
round-trip，最後才可開始極小 zh-TW ledger。

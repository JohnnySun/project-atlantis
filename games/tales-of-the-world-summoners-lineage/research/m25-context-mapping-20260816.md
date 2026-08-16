# A9PJ M25 context-derived glyph mapping boundary（2026-08-16）

M25 不改寫 M21 的 confirmed map，只把兩個有多層但尚未 runtime-backed 的 glyph
candidate 分開保存為 `context-provisional`：`0x000C → ー` 與 `0x00A8 → ッ`。工具
輸出只有 keyboard table position、24-byte record hash／bitmap count、direct static
caller occurrence counts 與 gate；不輸出 stream、原文、圖片或 OCR。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m25_context_mapping_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m25-context/summary.json
```

版本為 `m25-context-mapping-probe-20260816.v1`。A9PJ ROM SHA-256 應為
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。

## 證據分層

- `0x000C` 出現在 hiragana page 的固定 table slot `row=0, selection=59`；M19 private
  keyboard render 對應該頁的長音符位置，且 M24 direct candidate 中有重複的 katakana
  landmark context。這是 keyboard/table arithmetic + phrase context，仍不是 runtime
  tile byte identity。
- `0x00A8` 出現在 katakana page 的固定 table slot `row=1, selection=56`；M25 receipt
  顯示 8 個 distinct direct stream targets 帶有同一 code unit，且其 record raster 與 small-kana
  phrase context 一致。因 katakana page 本輪沒有 fresh runtime tile capture，仍只列
  context-provisional。
- M25 gate 明確增加 `0` confirmed identities；不把 `0x000C` 的 parser-independent
  font record 誤標成 `0xFF70` control，也不把 `0x00A8` 的 Unicode candidate 寫入
  translation ledger。

## private aggregate receipt

工具執行後應保存兩個 candidate 的 `record_sha256`、`record_ink_bit_count`、direct
caller／occurrence／target counts。這些欄位可驗證後續 decoder 是否漂移，但不含 source
text；M24 的 46 static caller rows、28 targets 仍沒有 runtime scene role。

## 下一個最小缺口

在可用 fresh A9PJ listener 下，對一個 direct candidate 或同一 keyboard page 取得
runtime table read／screen tile metadata，並用兩條以上獨立完整句子的 raster/context
alignment 交叉 `0x000C`／`0x00A8`。通過前維持 context-provisional，source checksum、
ledger 與翻譯仍關閉。

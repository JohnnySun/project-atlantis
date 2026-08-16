# M3 custom glyph slot audit：bounded planning only

日期：2026-08-16（Asia/Taipei）

這個切片只為缺字設計建立可審核的 slot-preservation 輸入；不選定 custom mapping、
不產生字型、不修改 ROM，也不把 source table、glyph bytes 或圖片寫入 Git。

## confirmed

- `font_slot_audit.py` 讀取 ignored 四池 decoded source table，對 259 筆 source records
  計算 strict Shift-JIS double-byte code units；此次 source pool cohort 的 used unique
  count 為 `228`，undecodable record count 為 `0`。
- codepage 有 `1834` entries；audit 只保留不在這個 bounded source-pool cohort 使用、
  且 raw pair 落在 reviewed Shift-JIS lead/trail ranges 的候選，執行 `candidate-limit=8`
  時取得 `8` 個候選。每個候選只輸出 codepage index、raw code unit、兩組 plane hash
  和 selector-zero expanded hash；報告明確標記 `candidate_slots_are_unapproved`。
- requested U+7D93／U+9A57（臺灣繁體「經／驗」）的 Python Shift-JIS byte mapping 可
  表示為 `0xE353`／`0xE984`，但兩者不在本作現行 codepage membership；這與 batch 2
  font coverage 的 missing-codepage gate 一致。此處不把「可編碼」誤寫成「已有 glyph」。
- 目前候選只代表「未在已知四池出現」；既有 pool 外的開機圖、壓縮／資料區或尚未解出的
  文本仍可能使用同一 raw code unit，所以 audit 不得直接用來 patch。

## provisional／pending

- 候選 slot 的 source pool non-use 是 bounded negative evidence，不是全 ROM non-use
  證明；最後 mapping 需要完整 source extraction、code-flow／畫面覆蓋和 aliases 風險
  審核。
- 下一步若取得合法可再分發的 glyph source，應以 `font_glyph_format.py` 驗證兩組
  0x20-byte plane→0x80-byte cache hash，再以獨立 custom encoder／patch verifier 驗證
  code unit、原 slot preservation、兩組 glyph bank、自然／controlled runtime receipt。
  目前未取得或提交任何字型來源，故 `經／驗` 仍 withheld。

## 可重現命令

```text
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/sangokushi-eiketsuden/tools/font_slot_audit.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --unicode U+7D93,U+9A57 --candidate-limit 8 \
  --output /private/tmp/b3ej-slot-audit.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  games/sangokushi-eiketsuden/tools/test_font_slot_audit.py -v
```

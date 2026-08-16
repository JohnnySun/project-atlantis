# 《聖火降魔錄：封印之劍》日版（AFEJ）

本目錄只處理 GBA 日版《ファイアーエムブレム 封印の剣》（Fire Emblem: The Binding Blade）。原始 ROM 必須由貢獻者自行提供，僅放在被 Git 忽略的 `roms/`；本專案不保存 ROM、完整日文腳本、未授權字型或來源不明的大段原文。

## 目前狀態

截至 2026-08-16，工作樹中尚未有 `roms/base/AFEJ.gba`，因此以下項目尚未被本機 ROM 證實：

- ROM 標頭身分、實際 revision、CRC32、SHA-1／SHA-256。
- 劇情、支援對話、章節事件、單位／武器／技能與圖像文字的實際位置。
- 文本是否為固定表、指標表、腳本資料、壓縮資料或混合格式。
- 字型資料、字元 codepage、控制碼、行寬限制與可逆回插路徑。

公開 FEBuilderGBA 與 `fireemblem6j` 資料只作為待驗證的逆向參考，不取代日版 ROM，也不把既有英譯或 `.tbl` 當作翻譯來源。已知外部參考與其限制見 `research/recon-20260816.md`。

## 唯讀偵察

放入合法的本機 ROM 後，先執行：

```sh
python3 tools/recon_afej.py roms/base/AFEJ.gba --json-out work/afej-recon.json
```

工具只讀 ROM；輸出的 `work/afej-recon.json` 是本機偵察報告，不進 Git。它會記錄 GBA 標頭、校驗值、雜湊、標準 Shift-JIS 探針、ROM 內指標候選、BIOS 壓縮標頭候選及 4bpp 字形窗口的啟發式候選。候選不能單獨視為文本或字型證據，必須再以執行期畫面／VRAM 或可重現的字節交叉比對確認。

偵察完成後，遊戲專屬工具必須再提供：

1. 嚴格、可重跑的本機原文表 `research/afej-decoded.jsonl`（該檔案被忽略，不能提交）。
2. `work/` 中含原文的翻譯工作記錄。
3. 只含 `source_hash` 的 `translations/*.jsonl` ledger；只能由 `core/ledger/strip_translations.rb` 產生後提交。
4. 回插後重新抽取、BPS round-trip 與 mGBA 場景驗證；在此之前不得宣稱翻譯或可逆構建完成。

## 簡繁與術語

正式繁體目標是 `zh-TW`，不是未指定的 `zh-Hant`。初步臺灣社群慣用名保存在 `translations/glossary.zh-TW.tsv`；每個專名仍需在實際 ROM 語境中核對，來源分歧時保留分歧並標記，不自行創造音譯。

## 提交邊界

只可 stage 本目錄內的文件、工具、可公開研究筆記與不含原文的翻譯 ledger。不要使用 `git add -A`；ROM、`work/`、原文表、圖片、OCR 輸出與構建產物均留在本機。

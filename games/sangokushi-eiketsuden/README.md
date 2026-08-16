# 《三國志英傑傳》（三國志英傑伝）本地化工作區

本目錄只處理 GBA 日版《三國志英傑伝》，工作 slug 為
`sangokushi-eiketsuden`。上一輪候選資料曾把《英傑傳》和《孔明傳》合併；本工作區明確不建立、不修改《孔明傳》資料。

本遊戲採用 `docs/TRANSLATION-LEDGER.md` 的原文分離流程：日版 ROM、解出的原文、字型圖片、OCR 結果與工作記錄只留在本機；可提交的 `translations/*.jsonl` 只能保存 `source_hash` 和譯文，不得帶 `source` 原文欄位。

## 當前狀態（2026-08-16）

- **ROM 身分已核對**：委派提供的 ZIP 只有一個 ROM entry，解壓後為 4 MiB；本機 ignored 路徑為 `roms/base/B3EJ_JP_candidate.gba`。GBA header 為 `EIKETSUDEN`／`B3EJ`／maker `C8`／revision `0`，與公開 `B3EJ` 產品候選一致。
- **雜湊已記錄**：CRC32 `a4a1c956`、MD5 `76cccc133899422854687e672f335cbd`、SHA-1 `32b5eeb82b0ffa14adc54223fb9e423efe8a1aa4`、SHA-256 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`。header 儲存補數為 `0xe1`、依標準公式計算為 `0x13`，不相符；已原樣保留，沒有修補 ROM。
- **靜態文本線索已建立**：已確認可讀的標準 Shift-JIS 字串群、`0x00` 終止／`0x0A` 換行、格式參數與候選指標池；`research/recon-ledger.md` 僅記錄偏移、分類與證據，不保存完整原文。
- **執行期只完成有界 sanity check**：獨立 mGBA/GDB session 可讀取 ROM、IWRAM 與非空 VRAM，並觀察到 DMA 搬移；尚未定位穩定的文字呼叫、字型 glyph identity 或可逆回插路徑。
- **公開術語研究已建立**：`translations/glossary.zh-TW.tsv` 是待 ROM 畫面／上下文核對的臺灣繁體候選表，涵蓋武將、地名、兵種／官職、策略和戰役事件用語；`research/term-sources.md` 記錄來源交叉核對與爭議項目。
- **沒有翻譯批次**：尚未產生 `research/sangokushi-eiketsuden-decoded.jsonl`，也沒有任何可提交 ledger 記錄；因此不能宣稱已完成劇情翻譯或可逆回插。

## 可重現的唯讀工具

```text
python3 tools/inspect_rom.py roms/base/B3EJ_JP_candidate.gba
python3 tools/scan_text_pointers.py roms/base/B3EJ_JP_candidate.gba
python3 -m unittest tools/test_inspect_rom.py tools/test_scan_text_pointers.py
```

兩個工具都只輸出 metadata、偏移、計數和 pointer target 範圍，不輸出完整原始腳本，也不修改 ROM。

## 後續唯讀偵察順序

1. 以 `inspect_rom.py` 重跑 header、CRC32／MD5／SHA-1／SHA-256 和 bounded probes；產品候選與 ROM header 仍分開記錄。
2. 以 `scan_text_pointers.py` 重跑已審核的指標池候選；每個候選都要記錄偏移和判定理由，不把合法位元組模式直接當成文字。
3. 若要繼續，才以 mGBA／GDB 觀察實際文字渲染、VRAM tile／tilemap、字型搬移和執行期資料。需分開記錄「字型位址已定位」和「glyph identity 已確認」兩種進度。
4. 解出一小段可重現的字串結構後，建立遊戲專用解碼器，輸出本機 `research/sangokushi-eiketsuden-decoded.jsonl`：每行至少含 `string_id`、`locale`、`text`、`provenance`，並標記 confirmed／provisional／unmapped 證據層級。
5. 只從本機原文表透過 `core/ledger/restore_translations.rb` 產生 `work/` 工作記錄；翻譯完成後以 `core/ledger/strip_translations.rb` 產生可提交帳本，再跑 schema、安全檢查、重抽取和回插測試。

## 控制碼、排版與回插邊界

目前已由靜態資料支持標準 Shift-JIS、`0x00` 終止和 `0x0A` 換行；另觀察到候選 `ESC C6 %s` 格式序列及 `%s`／`%d`／`%u`／`%%` 參數。這些仍不是完整控制碼契約；字型格式、glyph identity、最大寬度／行數、壓縮使用方式和回插位置，必須等遊戲專用解碼與畫面交叉驗證後才可確認。不套用黃金太陽或光明之魂的格式假設。

## 公開研究的使用限制

公開攻略只用來建立臺灣繁體術語候選、章節／戰場索引和事件分類，不作為日版 ROM 原文或逐句翻譯來源。正式翻譯仍以日版 ROM 解碼結果為準；公開來源的完整腳本、攻略段落和 ROM 均不保存到 Git。

來源與術語決策記錄見 [`research/term-sources.md`](research/term-sources.md)；唯讀偵察帳見 [`research/recon-ledger.md`](research/recon-ledger.md)。

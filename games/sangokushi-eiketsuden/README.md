# 《三國志英傑傳》（三國志英傑伝）本地化工作區

本目錄只處理 GBA 日版《三國志英傑伝》，工作 slug 為
`sangokushi-eiketsuden`。上一輪候選資料曾把《英傑傳》和《孔明傳》合併；本工作區明確不建立、不修改《孔明傳》資料。

本遊戲採用 `docs/TRANSLATION-LEDGER.md` 的原文分離流程：日版 ROM、解出的原文、字型圖片、OCR 結果與工作記錄只留在本機；可提交的 `translations/*.jsonl` 只能保存 `source_hash` 和譯文，不得帶 `source` 原文欄位。

## 當前狀態（2026-08-16）

- **ROM 身分已核對**：委派提供的 ZIP 只有一個 ROM entry，解壓後為 4 MiB；本機 ignored 路徑為 `roms/base/B3EJ_JP_candidate.gba`。GBA header 為 `EIKETSUDEN`／`B3EJ`／maker `C8`／revision `0`，與公開 `B3EJ` 產品候選一致。
- **雜湊已記錄**：CRC32 `a4a1c956`、MD5 `76cccc133899422854687e672f335cbd`、SHA-1 `32b5eeb82b0ffa14adc54223fb9e423efe8a1aa4`、SHA-256 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`。header 儲存補數為 `0xe1`、依標準公式計算為 `0x13`，不相符；已原樣保留，沒有修補 ROM。
- **靜態文本線索已建立**：已確認可讀的標準 Shift-JIS 字串群、`0x00` 終止／`0x0A` 換行、格式參數與候選指標池；`research/recon-ledger.md` 僅記錄偏移、分類與證據，不保存完整原文。
- **執行期已完成標題畫面有界 capture**：使用共用 `core/gba` 工具在獨立 mGBA/GDB session 讀取 ROM、IWRAM、VRAM、OAM 與 palette，確認 Mode 0 下 BG0–BG3 的 screenbase，並以共用 renderer 重建出開始提示、版權列、日文標題圖樣與裝飾層；尚未把靜態 Shift-JIS 字串池連到文字呼叫、字型 glyph identity 或可逆回插路徑。
- **M2.1 static consumer chain（2026-08-16）已完成有界切片**：table B file base `0x0D1FFC` 有 44 個指標、26 個唯一 record target，連續範圍至 `0x0D20AC`，下一個 word 為零，鄰接 table C 從 `0x0D20D8` 開始。已證實 Thumb consumer `0x080262F8` 取 table base、`0x080262FA–0x08026306` 做 index mask／scale／record load，再呼叫 `0x0800D8F0` → `0x0800D3FC` 的 wrapper／byte formatter；這條證據止於 reader／formatter，尚未證實 glyph writer。呼叫端目前只證實 `index & 0x7f`，沒有 `<44` bound。工具、分類與 runtime pending 見 `research/m2-1-static-chain-20260816.md`。
- **M2.2 static text→glyph chain（2026-08-16）已完成有界切片**：`0x0800D3FC` 建立 stack output buffer `sp+0x18`，經 `0x0806ED80: bx r2` veneer 解析到 `0x0800CAD8` output writer；SJIS double-byte path `0x0800CB62` → `0x08008D18` → codepage lookup `0x080650A4` → glyph expand `0x080650DC` → 128-byte cache `0x02000000` → VRAM copy `0x080656D4`／tilemap `0x08008914` 均已由有效 Thumb span、literal pool 與 callsite 驗證。codepage table 是 file `0x024110C` 的 1834 entries；glyph source 是 `base + codepage_table_index * 0x20`，不是直接以 raw Shift-JIS code 索引。三個 strict SJIS sentinel（U+90E8、U+306B、U+529B）已有 source byte、codepage index 與兩組 static glyph chunk hash 的交叉證據；runtime glyph hit 仍 pending。event index 仍只有 local `u16(r6+0x02)` bound，`<44` 未證明；`trace_m2_runtime.py --pipeline --controlled-record` 已加入但本次 headless listener 未產生可用 report，沒有把 controlled 或 natural hit 冒充 confirmed。完整 offsets、hash、confirmed／provisional／negative 分類見 `research/m2-2-static-pipeline-20260816.md`。
- **公開術語研究已建立**：`translations/glossary.zh-TW.tsv` 是待 ROM 畫面／上下文核對的臺灣繁體候選表，涵蓋武將、地名、兵種／官職、策略和戰役事件用語；`research/term-sources.md` 記錄來源交叉核對與爭議項目。
- **沒有翻譯批次**：`research/sangokushi-eiketsuden-decoded.jsonl` 只在本機 ignored 路徑作為 bounded extractor 輸出，含原文但不進 Git；沒有任何可提交 ledger 記錄，因此不能宣稱已完成劇情翻譯或可逆回插。

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

目前已由靜態資料支持標準 Shift-JIS、`0x00` 終止和 `0x0A` 換行；另觀察到候選 `ESC C6 %s` 格式序列及 `%s`／`%d`／`%u`／`%%` 參數。M2.2 已確認一條 SJIS codepage 到 static glyph source/cache/VRAM writer 的 addressing 鏈，但尚未確認 runtime glyph identity、完整控制碼契約、最大寬度／行數、壓縮使用方式或回插位置。不套用黃金太陽或光明之魂的格式假設。

## 公開研究的使用限制

公開攻略只用來建立臺灣繁體術語候選、章節／戰場索引和事件分類，不作為日版 ROM 原文或逐句翻譯來源。正式翻譯仍以日版 ROM 解碼結果為準；公開來源的完整腳本、攻略段落和 ROM 均不保存到 Git。

來源與術語決策記錄見 [`research/term-sources.md`](research/term-sources.md)；唯讀偵察帳見 [`research/recon-ledger.md`](research/recon-ledger.md)。

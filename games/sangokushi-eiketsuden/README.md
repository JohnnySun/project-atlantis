# 《三國志英傑傳》（三國志英傑伝）本地化工作區

本目錄只處理 GBA 日版《三國志英傑伝》，工作 slug 為
`sangokushi-eiketsuden`。上一輪候選資料曾把《英傑傳》和《孔明傳》合併；本工作區明確不建立、不修改《孔明傳》資料。

本遊戲採用 `docs/TRANSLATION-LEDGER.md` 的原文分離流程：日版 ROM、解出的原文、字型圖片、OCR 結果與工作記錄只留在本機；可提交的 `translations/*.jsonl` 只能保存 `source_hash` 和譯文，不得帶 `source` 原文欄位。

## 當前狀態（2026-08-16）

- **ROM 身分已核對**：委派提供的 ZIP 只有一個 ROM entry，解壓後為 4 MiB；本機 ignored 路徑為 `roms/base/B3EJ_JP_candidate.gba`。GBA header 為 `EIKETSUDEN`／`B3EJ`／maker `C8`／revision `0`，與公開 `B3EJ` 產品候選一致。
- **雜湊已記錄**：CRC32 `a4a1c956`、MD5 `76cccc133899422854687e672f335cbd`、SHA-1 `32b5eeb82b0ffa14adc54223fb9e423efe8a1aa4`、SHA-256 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`。header 儲存補數為 `0xe1`、依標準公式計算為 `0x13`，不相符；已原樣保留，沒有修補 ROM。
- **靜態文本線索已建立**：已確認可讀的標準 Shift-JIS 字串群、`0x00` 終止／`0x0A` 換行、格式參數與候選指標池；`research/recon-ledger.md` 僅記錄偏移、分類與證據，不保存完整原文。
- **四組 bounded text-pool decoder（2026-08-16）已完成**：`tools/extract_text_pools.py` 對 A `0x0CBC54/183`、B `0x0D1FFC/44`、C `0x0D20D8/4`、D `0x0D4D00/28` 做 explicit pointer／NUL／Shift-JIS 驗證，產生 ignored `research/sangokushi-eiketsuden-decoded.jsonl`；metadata 顯示 A 183/183、B 44/44、C 4/4、D 28/28 可解，A 有 177 筆 LF，未發現 opaque control byte。這是結構與 decoder 證據，不把四池直接宣稱為完整劇情或自然畫面文本。
- **執行期已完成標題畫面有界 capture**：使用共用 `core/gba` 工具在獨立 mGBA/GDB session 讀取 ROM、IWRAM、VRAM、OAM 與 palette，確認 Mode 0 下 BG0–BG3 的 screenbase，並以共用 renderer 重建出開始提示、版權列、日文標題圖樣與裝飾層；尚未把靜態 Shift-JIS 字串池連到文字呼叫、字型 glyph identity 或可逆回插路徑。
- **M2.1 static consumer chain（2026-08-16）已完成有界切片**：table B file base `0x0D1FFC` 有 44 個指標、26 個唯一 record target，連續範圍至 `0x0D20AC`，下一個 word 為零，鄰接 table C 從 `0x0D20D8` 開始。已證實 Thumb consumer `0x080262F8` 取 table base、`0x080262FA–0x08026306` 做 index mask／scale／record load，再呼叫 `0x0800D8F0` → `0x0800D3FC` 的 wrapper／byte formatter；這條證據止於 reader／formatter，尚未證實 glyph writer。呼叫端目前只證實 `index & 0x7f`，沒有 `<44` bound。工具、分類與 runtime pending 見 `research/m2-1-static-chain-20260816.md`。
- **M2.2 static text→glyph chain（2026-08-16）已完成有界切片**：`0x0800D3FC` 建立 stack output buffer `sp+0x18`，經 `0x0806ED80: bx r2` veneer 解析到 `0x0800CAD8` output writer；SJIS double-byte path `0x0800CB62` → `0x08008D18` → codepage lookup `0x080650A4` → glyph expand `0x080650DC` → 128-byte cache `0x02000000` → VRAM copy `0x080656D4`／tilemap `0x08008914` 均已由有效 Thumb span、literal pool 與 callsite 驗證。codepage table 是 file `0x024110C` 的 1834 entries；glyph source 是 `base + codepage_table_index * 0x20`，不是直接以 raw Shift-JIS code 索引。三個 strict SJIS sentinel（U+90E8、U+306B、U+529B）已有 source byte、codepage index 與兩組 static glyph chunk hash 的交叉證據；M2.3 再取得 controlled runtime edge。event index 仍只有 local `u16(r6+0x02)` bound，`<44` 未證明。完整 offsets、hash、confirmed／provisional／negative 分類見 `research/m2-2-static-pipeline-20260816.md`。
- **M2.3 runtime gate（2026-08-16）完成受控有界收據**：static upstream 已證實 `0x08026510 → 0x0801929C` builder、`r6+0x02` count 與 `r6+0x1C` event buffer；empty path 固定 44，normal path仍由 runtime table `0x02014E78` 的 `0xFF` 終止。32-event natural slice 沒有 consumer hit；一筆明確標記的 controlled consumer fixture 觀察到 actual index `0 < 44`，並以 B[0] `0x08078528` 取得 formatter `0x0800D3FC` → writer `0x0800CAD8` → glyph cache `0x02000000` → VRAM `0x0600C080`（128-byte hash 同值）→ tilemap `0x02013050` 收據。`0x9594` 的 runtime codepage index `1301`／Unicode identity `U+90E8` 已交叉核對；自然全域 index gate、U+306B／U+529B runtime identity 與 ROM 回插仍 pending。詳見 `research/m2-3-runtime-gate-20260816.md`。
- **M2.4 natural cohort／state gate（2026-08-16）已完成有界負證據與靜態收尾**：兩條 fresh-process、single-connection 的 32-event natural paths（`none:8,start:4,none:20` 與 `none:4,start:8,none:20`）都停在 title/input-read loop；builder、consumer、formatter、writer 全為 0，VRAM before/after hash 相同，自然 cohort 為 0。`tools/m2_4_static.py` 進一步證實 initializer `r6+0x10` 的 consumer pointer 經 `0x0801A738` state gate、`0x0801A12C` poll，再由 `0x0806ED80: bx r2` 間接進入 `0x08026054`；`r6+0x14` 來自 `0x08021A44` 對 EWRAM table `0x0203544C` 的 nonzero predicate。確切 menu／battle 語意與自然 event index `<44` 仍 unknown。完整分欄與報告欄位見 `research/m2-4-natural-cohort-20260816.md`。
- **公開術語研究已建立**：`translations/glossary.zh-TW.tsv` 是待 ROM 畫面／上下文核對的臺灣繁體候選表，涵蓋武將、地名、兵種／官職、策略和戰役事件用語；`research/term-sources.md` 記錄來源交叉核對與爭議項目。
- **第一個 bounded translation ledger（2026-08-16）已建立**：`translations/table-b-batch-1.jsonl`
  只含 Table B B0–B5 六筆不含 `source` 的 `zh-TW`／schema ledger，狀態為 `ai_review`；
  restore→strip 逐 byte 相同，未把 ignored 原文、work 或 ROM 納入 Git。這是結構完整的
  fixed-slot 靜態批次，不宣稱自然畫面 reachability 或整部劇情翻譯完成。
- **第一個 bounded insertion／BPS receipt 已完成**：`font_coverage.py` 對 6/6 目標通過
  strict Shift-JIS、1834-entry codepage、兩組 0x20-byte glyph slot 和原槽位長度檢查；
  `patch_table_b.py` 只改 6 個 unique Table B record、42 bytes，不移動 pointer table。
  `verify_table_b_patch.py` 重新抽取 6/6 相符，BPS 套用結果與 patched ROM byte-for-byte
  相同。完整 hash／CRC／限制見 `research/m3-batch1-roundtrip-20260816.md`。

## 可重現的唯讀工具

```text
python3 tools/inspect_rom.py roms/base/B3EJ_JP_candidate.gba
python3 tools/scan_text_pointers.py roms/base/B3EJ_JP_candidate.gba
python3 -m unittest tools/test_inspect_rom.py tools/test_scan_text_pointers.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/extract_text_pools.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-all-source.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 tools/m2_4_static.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-m24-static.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p 'test*.py' -v
```

兩個工具都只輸出 metadata、偏移、計數和 pointer target 範圍，不輸出完整原始腳本，也不修改 ROM。

## 後續唯讀偵察順序

1. 以 `inspect_rom.py` 重跑 header、CRC32／MD5／SHA-1／SHA-256 和 bounded probes；產品候選與 ROM header 仍分開記錄。
2. 以 `scan_text_pointers.py` 重跑已審核的指標池候選；每個候選都要記錄偏移和判定理由，不把合法位元組模式直接當成文字。
3. 若要繼續，才以 mGBA／GDB 觀察實際文字渲染、VRAM tile／tilemap、字型搬移和執行期資料。需分開記錄「字型位址已定位」和「glyph identity 已確認」兩種進度。
4. 解出一小段可重現的字串結構後，建立遊戲專用解碼器，輸出本機 `research/sangokushi-eiketsuden-decoded.jsonl`：每行至少含 `string_id`、`locale`、`text`、`provenance`，並標記 confirmed／provisional／unmapped 證據層級。四池 decoder 已完成 bounded metadata；完整畫面語意仍待核對。
5. 只從本機原文表透過 `core/ledger/restore_translations.rb` 產生 `work/` 工作記錄；翻譯完成後以 `core/ledger/strip_translations.rb` 產生可提交帳本，再跑 schema、安全檢查、重抽取和回插測試。B0–B5 已完成這條 bounded 流程；全量仍待完成。

## 控制碼、排版與回插邊界

目前已由靜態資料支持標準 Shift-JIS、`0x00` 終止和 `0x0A` 換行；另觀察到候選 `ESC C6 %s` 格式序列及 `%s`／`%d`／`%u`／`%%` 參數。M2.3 已以 controlled call 確認一條 runtime formatter→glyph cache→128-byte VRAM copy→tilemap edge，並確認 U+90E8 的 codepage identity；M2.4 static caller chain 已把 normal dispatch 的 state gate 與 indirect consumer edge 固定，但兩條 bounded natural path 尚未跨過 gate。B0–B5 的 encoder 只接受 strict Shift-JIS、既有 codepage entry、固定槽位與無控制碼目標；這不等於自然畫面 reachability、完整控制碼契約、最大寬度／行數、壓縮使用方式或全遊戲回插位置。不套用黃金太陽或光明之魂的格式假設。

## 公開研究的使用限制

公開攻略只用來建立臺灣繁體術語候選、章節／戰場索引和事件分類，不作為日版 ROM 原文或逐句翻譯來源。正式翻譯仍以日版 ROM 解碼結果為準；公開來源的完整腳本、攻略段落和 ROM 均不保存到 Git。

來源與術語決策記錄見 [`research/term-sources.md`](research/term-sources.md)；唯讀偵察帳見 [`research/recon-ledger.md`](research/recon-ledger.md)。

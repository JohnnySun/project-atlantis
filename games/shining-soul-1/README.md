# 《光明之魂》（シャイニング・ソウル）漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、抽出的原文、渲染出的字形圖片及實驗構建只保存在本機，不進入 Git；本遊戲使用 `docs/TRANSLATION-LEDGER.md` 定義的帳本方案（`core/ledger/strip_translations.rb`／`restore_translations.rb`），**不採用**兩款黃金太陽既有的「工作記錄直接進 Git」格式。

這是 `gba-localization` skill（`.agents/skills/gba-localization/SKILL.md`）第一次在全新遊戲上實際使用。**開工前只需要讀完這份現狀摘要**——完整的逐輪偵察過程、每個結論怎麼得出、繞過哪些錯誤路線，都在 `SESSION-LOG.md`，那是參考資料，不是必讀清單；需要理解「某個結論的證據鏈」或「某個方法之前試過為什麼失敗」時才回去查對應章節。逐主題的詳細分析另外拆在 `research/*.md`（見下方引用）。

## 現狀摘要（第二十輪之後）

### 文字系統：結構已解，字符身分覆蓋中

- **字串格式**：NUL（`0x0000`）結尾的 16-bit 代碼陣列。每個代碼 `category = (code>>8)&0xF`（字形池選擇器）、`glyph_entry_index = (code&0xFF)-1`（池內索引）。見 `research/obj-sentence-string-format.md`。
- **五張 OBJ 字形像素表**，全部同一公式 `glyph_rom_offset(index) = base + index*0x80`：

  | category | base | 內容 |
  | --- | --- | --- |
  | 0 | `0x46abe4` | 平假名（0–70，標準五十音序）＋小字假名＋片假名＋符號／Latin／數字（151+，見 `PUNCT_LATIN_CHAR_IDX`） |
  | 1 | `0x474584` | 漢字 |
  | 2 | `0x47dfa4` | 漢字 |
  | 3 | `0x4879c4` | 漢字 |
  | 4 | `0x4913e4` | 漢字＋RPG 屬性縮寫圖示（index 1–15），index 39 後截止 |

  category 5–15：**已確認這個 JP ROM 版本沒有接上任何字形池**（開機期 IWRAM `0x030065f0` 查表恆為 NULL＋全 ROM 語料掃描交叉驗證），不是「還沒解出」。見 `research/obj-sentence-category4-and-dispatch-table.md`。
- **另外兩張獨立的 BG tilemap 字型表**（存檔選擇／姓名輸入畫面用，非 OBJ 句子系統）：`0x1398e8`（UI，168 格非空）、`0x1316e8`（姓名輸入鍵盤，987 格非空）——這兩張表是「tilemap tile-index 直接＝字符代碼」，不是上面的 16-bit 代碼格式，兩套系統目前未驗證是否有關聯。見 `research/bg-fonttable-codepage-partial.md`、`research/name-entry-hiragana-codepage.md`。
- **字串池**（不需指標表，逐一走訪即可枚舉）：對話／提示句池 `0x499a04` 起（182 個池／620 個條目／2,150 行）、怪物名稱表 `0x460b78` 起（109 個池／242 個條目／487 行）。全 ROM 掃描過兩次確認沒有其他真實文字池。見 `research/obj-sentence-string-pool.md`。
- **兩層覆蓋率，不要混為一談**：
  - **代碼層級**（這個代碼屬於哪個已知系統）：category 0/1/2/3/4 合計涵蓋語料庫 99.97% 的代碼——這只代表「知道去哪張表找像素」。
  - **身分層級**（知道那個像素是哪個 Unicode 字）：目前 `tools/decode_strings.py` 對 222 筆解碼記錄，**41 筆（18.5%）完全無佔位符**，其餘仍帶至少一個 `{unmapped_glyph:category:index}`。已知身分：12 個 confirmed（獨立位址交叉驗證）＋約 30 個 provisional（OCR 統計投票或直接像素判讀，見下）。**這是目前最大的持續工作項目**。

### 已知未解 / 暫緩事項

- ~~**category 5–15 容量擴充**（暫緩）~~ —— **第二十輪已解除**，見下方「字形容量擴充」。
- **怪物名稱表前綴之謎**：怪物名前穩定帶 1–2 字元前綴（如「ぬそオオコウモリ」），結構已釐清但語意未解，翻譯批次刻意迴避。見 `SESSION-LOG.md` 第十四輪。
- category 4 表的精確上界（index 39 後是否還有內容）、BG 系統是否也用 16-bit 代碼格式，皆未驗證。

### 已完成的寫入驗證（proof of concept）

第十五輪已證實可以把翻譯文字寫回 ROM 並在遊戲裡正常渲染：插入 2 個中文字形（GNU Unifont 轉換）＋改寫一則已知字串，mGBA 實機渲染確認「道具」正確顯示、相鄰內容不受影響。見 `SESSION-LOG.md` 第十五輪、`tools/build_cn_glyph_poc.py`。

### 字形容量擴充：已打通（第二十輪，實機驗證通過）

第十五輪 POC 受限於 category 4 殘餘的 215 個空格位。**第二十輪證實可以整類新增 category**，
`tools/build_cn_glyph_category5_poc.py` 實機驗證：職業選擇畫面經由全新的 category 5 正確
渲染出中文「字型」，既有五類、相鄰字串、其餘畫面元素全部不受影響。機制是——在確認全 `0xFF`
的 `0x660000+` 空白區蓋一張新的 type-8 資源標頭（count=6）、附一個新 category struct
（**必須整段照抄既有的 6,176-byte 前綴**，只寫首字組會讓 OBJ 圖層整片壞掉，這是第十六輪
遺留版本的實際缺陷）、再把 `0x080fa510` 這**一個**註冊表字組指過去。不動既有五類任何位元組、
不改任何可執行碼。

**容量**：每類 256 格（由 struct 前綴 `word[1]=0x9820` 宣告），category 5–15 共 11 類未用
→ 最多 **2,805 格**（每類可定址 255 格：代碼低位元組 0x01–0xFF ⇒ 索引 0–254，0x00 是字串終止碼；struct 宣告的第 256 格存在於儲存空間但無法被指名）。詳見 `SESSION-LOG.md` 第二十輪。

### 通用編碼器：已可用（第二十輪，實機驗證通過）

`tools/build_translation_rom.py` 把上面的機制從一次性 POC 變成完整管線：讀取帳本工作記錄
（`work/*.jsonl`）→ 收集相異字元 → 配置到新 category 的槽位 → 插入字形點陣 → 就地改寫字串
代碼陣列 → 輸出 ROM。

```sh
python3 games/shining-soul-1/tools/build_translation_rom.py \
  --rom games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba \
  --out games/shining-soul-1/roms/build/ss1-zh-tw.gba \
  --locale zh-TW --batch 'games/shining-soul-1/work/*.jsonl'
```

目前實績：23 筆已翻譯記錄中 **21 筆成功寫入**（70 個相異字元，全部裝進 category 5，
剩餘 2,735 格空間），mGBA 實機確認職業選擇畫面顯示「請選擇職業」、顏色選擇畫面顯示
「請選擇顏色」。**fail-closed**：放不下的記錄一律跳過並列出原因，絕不溢出到下一個條目——
本次 2 筆跳過（一筆 marker 宣告 2 行但譯文只有 1 行、一筆超出預算 2 bytes）。

**字寬**：本輪量測發現遊戲自己的漢字墨水寬度上限恰為 13px，與 sprite 前進距離 13px 相同；
GNU Unifont 的 CJK 字形是 15px，直接插入會讓每個字與鄰字重疊 2px（第一次端到端渲染已實際
出現）。編碼器預設用 LANCZOS＋門檻把字形壓縮到 13px（`--ink-width`，設 0 可停用），壓縮後
字距與原文一致且字形仍清晰。

**尚未做到**：字串**變長**時的安置解法仍未解——本遊戲沒有指標表、字串池位置固定，
目前只能在既有預算內改寫，譯文長於預算就只能跳過或改短。

### 已提交的翻譯帳本（4 批，23 筆）

`games/shining-soul-1/translations/`：`ui-strings-first-batch.jsonl`（8）、`battle-status-batch.jsonl`（2）、`npc-dialogue-batch2.jsonl`（10）、`item-system-batch.jsonl`（3）。全部經過 schema 驗證、`restore(strip(x))==x` 往返核對、`scripts/check-repository-safety.rb` 通過，不含原文（`source_hash` 取代 `source.text`）。

## 中文譯名核對

`game.yml` 的 `zh-Hans`／`zh-TW` 標題採用「光明之魂」，依專案「專有名詞音譯政策」核對後決定：巴哈姆特 ACG 資料庫（`acg.gamer.com.tw`，條目 `s=3915`）明確使用「光明之魂」；另有多個獨立中文遊戲站台（`indienova.com`、`99danji.com`、`sptuner.blogspot.com` 等）不約而同使用同一譯名，未發現任何分歧版本。維基百科中文版似乎沒有這款遊戲的獨立條目，因此未能取得政策要求的「Wikipedia＋巴哈姆特」雙來源中的 Wikipedia 那一份；但多個獨立巴哈姆特以外站台一致無異議，已達到政策「不只看單一來源」的精神，故採用「光明之魂」而非留白或自創音譯。

`titles.ja` 的「シャイニング・ソウル」是常見寫法，但**未經 ROM 驗證**——卡匣標頭的標題欄位是純 ASCII `SHINING SOUL`，沒有片假名資訊可比對。

## ROM 識別

| 項目 | 值 |
| --- | --- |
| 目錄檔名 | `0379 - 光明之魂1 Shining Soul(JP)(Sega)(64Mb).zip`（原始檔名以 GBK 編碼儲存，非 UTF-8，`unzip` 直接解壓會因編碼不符報 `Illegal byte sequence`，須改用能指定來源編碼的工具，如 Python `zipfile` + 手動 `cp437→gbk` 轉碼） |
| 卡匣標頭標題（offset `0xA0`,12 bytes） | `SHINING SOUL` |
| game code（offset `0xAC`,4 bytes） | `AHUJ` |
| maker code（offset `0xB0`,2 bytes） | `8P` |
| 標頭固定值（offset `0xB2`） | `0x96`（正確） |
| 標頭補數校驗（offset `0xBD`） | `0x2e`，與 `-(sum(0xA0..0xBC)) - 0x19` 計算值相符 |
| 檔案大小 | 8,388,608 bytes（0x800000） |
| CRC32 | `521450d1` |
| MD5 | `0cb9989beb289f843cdb69bb0bd8c8be` |
| SHA-1 | `5fe69468dc1ecd9fb40f0ab3ca361963006dbb02` |
| SHA-256 | `7adebc47af58a7cb12c6e862482e3fd1b2cb82aab2dc3a556ac93f9e78df6b28` |
| ROM 實際使用範圍 | `0x000000`–約 `0x660000`；`0x660000`–`0x800000` 全為 `0xFF` 填充（proof of concept 尚未使用這段空間） |

以上雜湊只是本機記錄，**未與任何 No-Intro／GoodGBA 等外部資料庫核對**。

## 工具清單

全部在 `games/shining-soul-1/tools/`。純靜態（讀 ROM 檔案，不需模擬器）：`scan_compression_signatures.py`、`scan_swi_calls.py`、`scan_pointer_tables.py`、`scan_sjis_runs.py`、`disasm_swi_calls.py`（需要 `/usr/bin/python3`，capstone 只裝在這個直譯器上）、`scan_sentence_strings.py`、`extract_string_pool.py`、`scan_string_pools.py`、`scan_category_stats.py`、`decode_strings.py`（原文表抽取器）、`ocr_render_lines.py`／`ocr_prepare_corpus.py`／`ocr_align_vote.py`／`ocr_contact_sheet.py`（OCR＋投票管線）。**會寫出 ROM 檔案的三支**（都只寫新的輸出檔，不改基準 ROM）：`build_translation_rom.py`（第二十輪，**通用編碼器，日常構建用這支**）、`build_cn_glyph_poc.py`（第十五輪，填 category 4 殘餘空格位）、`build_cn_glyph_category5_poc.py`（第二十輪，整類新增 category 5 的機制驗證，同時是編碼器的字形／常數來源模組）。

需要背景啟動 `mgba -g games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba`（連線前先 `ps aux | grep mgba` 確認沒有殘留的孤兒行程）：`gdbstub_client.py`（GDB stub 用戶端函式庫）、`render_vram_tiles.py`、`navigate_and_dump.py`、`extract_bg_fonttable.py`、`navigate_to_char_create.py`、`extract_obj_kana_fonttable.py`、`trace_sentence_glyph_load.py`、`trace_glyph_source_array.py`、`trace_sentence_string_source.py`、`extract_kanji_fonttable.py`、`render_string_glyphs.py`、`dump_category_dispatch_table.py`、`hijack_and_capture_glyph_sources.py`、`render_oam_composite.py`、`trace_dispatch_table_init.py`（第十六輪，追 IWRAM 查表初始化）。

**注意（第二十輪）**：`-g` 的 GDB 埠是編譯期常數，`-C ports.qt.gdbPort` 在 SDL／headless 路徑上無效；這台機器同時有其他遊戲的 agent 在跑 mGBA，必須自行編一份改埠的 mGBA、啟動帶 `-l 0`，且**不可 `pkill mgba`**。詳見 `SESSION-LOG.md` 第二十輪「環境教訓」。

每支工具的參數、方法論限制、已知陷阱都寫在自己的 docstring 裡；用法範例與各工具對應到哪一輪偵察，見 `SESSION-LOG.md`「已完成的唯讀掃描」一節（仍保留在歷史紀錄裡，因為那裡連著方法論脈絡，搬過來只留指令反而失去上下文）。

## skill 使用備註

第二至十九輪累積的、對 `gba-localization` skill 有通用（非本遊戲專屬）參考價值的心得，已同步寫進 `.agents/skills/gba-localization/SKILL.md` 本身（不在這裡重複）——目前已收錄的主題包括：找不到文字結構時的分層偵察方法論、OCR＋語料庫統計投票的三層驗證（票數→外形→語境）、`research/` 目錄哪些東西真的受 `.gitignore` 保護、往上追呼叫鏈定位資料來源、IWRAM/EWRAM 執行期資料 vs. ROM 靜態資料的判斷、劫持已驗證呼叫鏈餵任意輸入、固定 stride 字形表的空格位掃描、點陣字型與遊戲格式的尺寸匹配。完整心得原文（含產生時的具體情境）留在 `SESSION-LOG.md` 對應輪次的「心得」小節。

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。渲染出的畫面／字形圖片一律留在本機（`research/**/*.png`，已由 `.gitignore` 排除），不進 Git。

詳見[路線圖](ROADMAP.md)、[逐輪偵察歷史](SESSION-LOG.md)。

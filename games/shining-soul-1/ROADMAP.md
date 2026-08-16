# 路線圖

## 里程碑 0：唯讀偵察（本輪）

- [x] 取得並校驗基準日版 ROM：解壓縮（zip 檔名為 GBK 編碼，非 UTF-8）、標頭欄位解析、標頭補數校驗、CRC32／MD5／SHA-1／SHA-256。
- [x] 以熵分析粗略劃分程式碼／圖形／填充區間，確認 ROM 實際使用範圍只到約 `0x660000`（其後到 `0x800000` 為 `0xFF` 填充）。
- [x] 排除「文字以未壓縮標準 Shift-JIS 直接存放」的假設——結構掃描的大量候選經人工檢視後幾乎全是圖形資料假陽性；常見日文 UI／戰鬥詞彙的精確位元組搜尋全部落空。
- [x] 掃描 BIOS 解壓縮呼叫點（`swi 0x10`–`0x18`）與字組對齊「壓縮簽章」候選，記錄候選數量與已知的高假陽性率，未反組譯驗證。
- [x] 掃描 ROM 位址範圍指標表候選，未找到典型字串表形狀。
- [x] 確認目前沒有公開的《光明之魂》GBA 文字格式逆向工程資料可參考。
- [x] **第二輪已完成**：用 capstone 反組譯覆核 BIOS 壓縮呼叫候選（結論：137 個候選全部無法確認為真指令，強化版負面結果）；用 `mgba --gdb` 即時觀察執行期 VRAM，確認標題畫面渲染內容、GBA 4bpp/32-bytes-per-tile 格式假設、以及片假名＋拉丁字母混排字形資料在 ROM `0x62AA44`–`0x62B8E4` 附近的位置（逐位元組比對確認未經 BIOS 壓縮）。詳見 `games/shining-soul-1/README.md`「第二輪偵察」一節。
- [x] **第三輪已完成**：對照 mGBA 0.10.5 原始碼確認直接寫 `KEYINPUT` 記憶體為何架構性無效（每次讀取都被 `keysActive`／`keyCallback` 覆寫）；改用讀取 watchpoint＋暫存器覆寫成功跳過標題畫面，一路推進並渲染確認到「模式選擇」「存檔選擇」兩個新畫面（見 `games/shining-soul-1/README.md`「第三輪偵察」一節，渲染圖存於 `research/mode-select-screen-obj-render.png`、`research/save-select-screen-bg2-char-stats-render.png`、`research/save-select-screen-bg3-file-slots-render.png`）；找到字型 tile 搬入 VRAM 使用的真實 `swi`（BIOS CpuSet／CpuFastSet）呼叫與其所屬的通用「傳輸佇列」flush 迴圈（ROM file offset 約 `0x11a0`–`0x11fe`）；一個「字型專屬推入函式」候選（`0x08001154`）經即時攔截測試後被**否定**（誠實記錄，非成功結論）。
- [~] **第四輪已完成部分**：直接反查存檔選擇畫面 BG2／BG3 tilemap 的 tile-index 陣列，建立約 32 個相異字符的部分 codepage（confirmed／中信心／低信心分級，見 `games/shining-soul-1/research/bg-fonttable-codepage-partial.md`）；並確認支撐這批 BG 文字渲染的 1024 格字型表本體位於 ROM `0x1398e8`–`0x1418e8`（窮舉逐格比對確認，tile-index 直接對應表內位址，無需另找間接對照層）。**尚未完成（第五輪已部分補上，見下）**：跨畫面驗證（是否為系統通用 codepage，而非單畫面美術表）、對話文字系統本身（本輪找到的兩張字型表都只涵蓋 UI／選單短字串，無 hiragana／漢字）。
- [x] **第五輪已完成**：從乾淨開機獨立重跑並驗證了 session 5 遺留但未核對的推進（存檔選擇 FILE1 → 職業選擇 → 顏色選擇），並新推進到**姓名輸入畫面**（`games/shining-soul-1/tools/navigate_to_char_create.py`，可重跑）。姓名輸入畫面用的是**第二張、全新的 1024 格 BG 字型表**（ROM `0x1316e8`–`0x1396e8`，987 格非空），與 `0x1398e8` 表不同，證實 VRAM charbase 0 依畫面動態換表、不是全域固定表。用該畫面的標準五十音鍵盤版面一次核對出 **71 個高信心平假名字符＋3 個模式切換圖示（あ／ア／A）**（`games/shining-soul-1/research/name-entry-hiragana-codepage.md`），首次涵蓋 hiragana。另外直接驗證了職業選擇／顏色選擇畫面沿用存檔選擇畫面的 `0x1398e8` 表（跨畫面共用的第一個正面證據），但第四輪「tile 96–108＝キャラクタ／カラーセンタク」的猜測在這兩個畫面未獲支持（誠實記錄的負面結果）；定位（但未完全解出定址規則）職業選擇畫面 OBJ 完整句子「職業を選んでください」所用字形在 ROM `0x46A000`–`0x48F000` 一帶、且未經壓縮。仍未解決：對話文字系統本身、OBJ 假名表的確切定址公式。
- [x] **第七輪已完成**：解出職業選擇畫面 OBJ 句子「職業を選んでください」用的字形定址機制——找到本遊戲規模最大的一張字型表（ROM `0x46abe4` 起，`index*0x80` 定址，平假名＋片假名＋Latin＋數字＋符號，7 點零自由參數驗證，見 `games/shining-soul-1/research/obj-sentence-glyph-loader.md`）；即時追蹤確認單字元繪製呼叫鏈——每字符一次 BIOS `CpuSet`/`CpuFastSet` 搬移 128 bytes，經共用的「傳輸佇列」enqueue 函式（ROM `0x08001154`，第三輪曾因測試情境不對而誤判否定，本輪翻案確認）、唯一呼叫點（ROM `0x080034d0`），且此呼叫點是逐一走訪本畫面全部 sprite（角色圖示＋「剣士」標籤＋完整句子共 13–14 個）的共用迴圈，直接證實存在真正可重用的文字/圖塊渲染系統。仍未解決：句子本身的字元代碼序列儲存位置（多種假設已測試為負面結果，見上）、漢字定址機制（確認不套用同一 index*0x80 公式）。
- [x] **第八輪已完成**：解出句子字元代碼序列本身的儲存格式——第七輪留下的最後一個核心缺口。從已知 enqueue 呼叫點（`0x080034d0`）往上追兩層呼叫者，找到真正的字串走訪迴圈（ROM file offset `0xe8f0`–`0xe944`），確認「職業を選んでください」以 NUL（`0x0000`）結尾的 16-bit 代碼陣列存在 ROM `0x499b1a`，「色を選んでください」存在 `0x499b3e`；解碼公式 `category=(code>>8)&0xF`／`glyph_entry_index=(code&0xFF)-1`，用兩畫面共用的「選んでください」尾段逐位元組相同做交叉驗證。附帶確認第五張獨立 ROM 表（字形描述子池 `0x469f60+char_idx*8`）。見 `games/shining-soul-1/research/obj-sentence-string-format.md`。仍未解決：漢字的 `glyph_entry_index` 定址規則、字串池區域的完整範圍、BG 系統是否用同一格式。
- [x] **第九輪已完成**：把第八輪解出的字串格式當結構特徵做全 ROM 靜態掃描（純唯讀，全程未啟動 mGBA），取代逐一用模擬器追出每個字串。重大發現：字串不是孤立存在，是排成連續的**字串池**——每個字串前有小標頭（`marker`＝行數 1–8，或帶 `id` 的 4-halfword 前綴），結束後零填充到下一個標頭，可從任一已知位址完整走訪列舉，不需要指標表（明確搜尋 3 個已知位址的 4-byte／3-byte 表示，全部零命中，指標表路線確認不存在或未找到）。找到並人工抽樣核對兩個高密度真實文字群聚區：對話／提示句池（ROM `0x499a04` 起，`0x499000`–`0x500000` 範圍內 182 個池、620 個條目、2,150 行，含完整可讀句子）與怪物／敵人名稱表（ROM `0x460b78` 起，242 個條目、487 行，含多個可辨識片假名怪物名）。全 ROM 套用同一套鏈式＋可讀性篩選後其餘 208 個池／504 個條目抽樣核對判斷幾乎全是假陽性，誠實記錄。附帶確認 `category` 欄位實際範圍是 0–15（不只第八輪見過的 0/2/3），多數值定址規則仍未解。新增三支唯讀工具（`scan_sentence_strings.py`／`extract_string_pool.py`／`scan_string_pools.py`）。見 `games/shining-soul-1/research/obj-sentence-string-pool.md`。仍未解決：多數 `category` 值定址規則、`id` 標頭語意、對話池內部穿插結構、怪物名稱表精確邊界。
- [x] **第十輪已完成**：解出 `category` 1／2／3 三個漢字字型表的定址公式（分別
  `0x474584`／`0x47dfa4`／`0x4879c4` + `index*0x80`，與 category 0 假名主表同一
  公式，只是 base 不同），各用兩個獨立資料點零自由參數驗證（category 1 用「剣士」
  標籤的剣/士，category 2 用職/色，category 3 用業/選）。用真實對話池的 6 句先前
  完全無法閱讀的句子做語意驗證，全部讀出通順日文（例：「名前を入力してください」
  「それは引き取れません」）。重新統計語料庫（9,645 個代碼）顯示 `category`
  0/1/2/3 四類已涵蓋 99.6%。新增兩支唯讀工具（`extract_kanji_fonttable.py`／
  `render_string_glyphs.py`）。見 `games/shining-soul-1/research/
  obj-sentence-kanji-categories.md`。仍未解決：`category` 4（次高頻率但只有單一
  資料點）與 6–15（樣本太少）。
- [x] **第十一輪已完成**：解出 `category` 4 的字型表定址公式（`0x4913e4 +
  index*0x80`，同一公式），用兩種完全獨立方法交叉驗證——(a) 反組譯字串走訪函式
  發現它實際查詢一張存在 **IWRAM**（`0x030065f0`，執行期資料，純靜態分析找不到）
  的 category 查表，連上執行中的 mGBA 直接讀出後，用已知 category 1/2/3 的像素表
  base 反推出「表項 + `0x1820`＝像素表 base」（三點零自由參數），套用到 category
  4 預測 base；(b) 劫持職業選擇畫面的字串渲染呼叫，強迫渲染任意真實語料庫字串，
  擷取逐字元來源位址，用兩個獨立真實語料庫字元（idx16/idx18）驗證，兩點零自由
  參數精確吻合方法 (a) 的預測值。5 句先前無法閱讀的真實句子渲染成完全通順、零
  缺口的日文。**同時確認 `category` 5–15 是這個 JP ROM 版本沒有接上任何字形池**
  （IWRAM 查表在兩個相隔多畫面的時間點皆恆為 NULL；全 ROM 重新掃描確認真實文字區
  內查無此類代碼，唯一例外是已識別的內部除錯字串）——這是任務明確允許的
  pattern-breaks 負面結果，不是「樣本不足待補」，不需要下一輪繼續嘗試。語料庫
  覆蓋率（0/1/2/3/4）達 99.97%（保守值）。新增三支工具
  （`dump_category_dispatch_table.py`／`hijack_and_capture_glyph_sources.py`／
  `scan_category_stats.py`）。見 `games/shining-soul-1/research/
  obj-sentence-category4-and-dispatch-table.md`。仍未解決：四張漢字表（cat1-4）
  的精確上界未窮舉；category 4 表項到像素表 base 的 `+0x1820` 偏移代表的完整
  資料結構未展開研究。

## 里程碑 1：文字系統與可逆試補丁

- [x] 反組譯覆核 BIOS 解壓縮呼叫候選——結論是全部候選都無法確認為真指令，「文字經 BIOS 常式解壓縮」目前沒有直接證據（但也未被排除，需要更完整的控制流重建才能真正排除）。
- [x] 找到字型／字形點陣資料——**第十一輪完成，OBJ-sentence 系統的全部有效 category 已解出**：OBJ 字型（title／模式選擇畫面，`0x62AA44`–`0x62B8E4`）位置與可重用性第二、三輪已確認（見上）。**第四輪新增**：找到並完整確認了第二張、獨立的 BG 字型表本體——ROM `0x1398e8`–`0x1418e8`（1024 格、`0x8000` bytes），存檔選擇畫面的 BG2／BG3 內容經窮舉逐格比對，與這整段 ROM 範圍逐位元組完全相同，涵蓋 tile-number 欄位能定址的全部範圍；tile-index 直接對應表內位址，這條渲染路徑上不存在需要另外尋找的間接 codepage 層。**第七輪新增**：找到並確認第四張、規模最大的字型表——ROM `0x46abe4` 起，`index*0x80` 線性定址，涵蓋平假名／片假名／Latin／數字／符號（至少 260 格），是職業選擇畫面完整句子「職業を選んでください」的字形來源，7 點零自由參數驗證，並用即時追蹤確認了完整的單字元繪製呼叫鏈（BIOS `CpuSet`/`CpuFastSet`→共用 enqueue 函式 `0x08001154`→唯一呼叫點 `0x080034d0` 的共用 sprite 繪製迴圈），見 `games/shining-soul-1/research/obj-sentence-glyph-loader.md`。四張表（OBJ 標題、BG×2、OBJ 主表）位置皆不同、彼此獨立，對話文字用哪一套仍未知；漢字的定址機制仍未解（不套用主表的 `index*0x80` 公式）。**第十輪新增**：解出三張獨立漢字表（`category` 1/2/3，base 分別 `0x474584`／`0x47dfa4`／`0x4879c4`，同一 `index*0x80` 公式），對話池文字現在絕大多數（99.6%）可完整渲染，見 `research/obj-sentence-kanji-categories.md`。**第十一輪完成**：解出第五張、最後一張有效表（`category` 4，base `0x4913e4`），並用即時讀取 IWRAM category 查表（`0x030065f0`）確認 `category` 5–15 這個 JP ROM 版本根本沒有接上任何字形池（不是「未解出」，是「不存在」），OBJ-sentence 系統的字形資料定位工作到此完整結束，見 `research/obj-sentence-category4-and-dispatch-table.md`。
- [~] 建立 provisional 碼表——**第四輪已建立部分**：直接反查存檔選擇畫面 BG2／BG3 tilemap tile-index，取得約 32 個相異字符的 confirmed／中信心／低信心分級碼表，見 `games/shining-soul-1/research/bg-fonttable-codepage-partial.md`。**第五輪大幅擴充**：姓名輸入畫面的標準五十音鍵盤版面一次核對出 71 個高信心平假名字符（見 `games/shining-soul-1/research/name-entry-hiragana-codepage.md`），總計兩張 BG 表加起來已有 100+ 個相異字符的 confirmed／中信心分級碼表，但**分屬兩張不同的 ROM 表**，尚未合併成單一系統碼表（因為 tile-index 本身不是全域穩定的，同一數字在不同表代表不同字符，見第五輪「重大結構修正」）。**第七輪新增**：OBJ 主表（`0x46abe4`）額外貢獻約 260 個相異字符（平假名／片假名／Latin／數字／符號），是目前規模最大的一張，但同樣是獨立於前兩張 BG 表的第三套碼表，尚未合併。OCR 路線目前仍判斷不需要，因為已知文字＋直接讀 tilemap／算式反推比 OCR 更精確。
- [~] 定位字串數量、分段方式與（若存在）指標表結構，寫出本遊戲專屬的抽取器——**第八輪重大推進**：已找到「哪個字元代碼對應哪個字形位址」的算式（`0x46abe4+index*0x80`）、「誰把字形搬進 VRAM」的完整呼叫鏈，**以及句子本身的字元代碼序列儲存格式**——NUL 結尾的 16-bit 代碼陣列，`category`＋`glyph_entry_index` 兩欄位解碼公式，已用兩個獨立畫面交叉驗證（見 `research/obj-sentence-string-format.md`）。**第九輪重大推進**：確認字串排列成連續可枚舉的**字串池**（標頭＋內容＋終止碼＋零填充），指標表明確搜尋為零命中（不存在或未找到，但不影響枚舉），寫出三支正式抽取／掃描工具（`scan_sentence_strings.py`／`extract_string_pool.py`／`scan_string_pools.py`，可從任一位址走訪整池或對全 ROM 做鏈式掃描），找到並人工核對約 862 個字串條目（對話池 620＋怪物名稱表 242），見 `research/obj-sentence-string-pool.md`。**尚未完成**：漢字與其餘 13 種 `category` 值的定址規則；`id`-前綴標頭的語意；對話池內部穿插結構與怪物名稱表精確邊界；把掃描結果正式轉成 `research/*-decoded.jsonl` 供帳本使用（目前輸出仍是掃描腳本的終端文字，未落成結構化原文表）。
- [x] 建立本機原文表 `research/shining-soul-1-decoded.jsonl`（`{"string_id", "locale", "text", "provenance"}`），供 `core/ledger/restore_translations.rb` 使用。**第十二輪完成**：新增 `games/shining-soul-1/tools/decode_strings.py`，走訪對話池（`0x499000`–`0x500000`）與怪物名稱表（`0x460000`–`0x46abe4`，收窄避開已知的 OBJ 字型像素表區以免誤讀圖形資料），套用第八輪解碼公式＋鏈式池發現＋一個沿用既有方法論的雜訊過濾器（一版有 bug——誤將條目內的正常結構性空行當雜訊、連帶丟掉真實多行對話，已修正，見 README「第十二輪偵察」），輸出 218 筆記錄（186 對話＋32 怪物名稱，3,888 個代碼、1,027 個 `unmapped_glyph:<category>:<index>` 佔位符）。明確區分三層信心：confirmed（gojuon 71 字＋12 個逐點驗證過的漢字身分）／provisional（片假名假說、促音、新發現的長音符「ー」＝char_idx 247，各自僅單點或假說支持，逐筆在 `provenance` 標註)／unmapped（其餘全部，含全部 category 5–15 與 12 個以外的所有漢字索引——已知有像素但無 Unicode 身分，如實佔位不猜）。25 筆（11.5%）零佔位符（12 筆 confirmed-only＋13 筆 provisional-only），193 筆（88.5%）至少 1 個佔位符——漢字覆蓋率遠低於字形定址覆蓋率的落差，如實反映「知道畫素位置」與「知道是哪個字」是兩回事。見 `research/shining-soul-1-decoded.jsonl`（本機、不進 Git）。**第十三輪部分推進**：執行 skill 文件化的「render + OCR + 語料庫統計投票」手法（本遊戲第一次真正執行，port 自 `games/golden-sun-the-lost-age/tools/infer_ja_codepage.rb`，唯讀未修改），267 行真實語料渲染＋Apple Vision OCR＋edit-distance 對齊投票，加上兩層驗收（ROM 像素 vs. 系統字型外形肉眼核對＋代入真實句子語意重讀核對——後者額外抓到 4 個純統計/外形都看不出問題的系統性誤讀，見 README「第十三輪偵察」），新增 23 個漢字身分（`KANJI_MAP_OCR_PROVISIONAL`，18 個 category 1＋4 個 category 3＋1 個上下文覆核），全部 provisional 分級、從不升級 confirmed。零佔位符記錄 25→29（11.5%→13.3%），`unmapped_glyph` 佔位符 1,027→837（↓18.5%）——確實推進但幅度有限，漢字表已知上百格非空資料裡仍只有一小部分（confirmed 12＋provisional 47）有身分，是本輪誠實記錄的殘留落差，非新缺口。**第十四輪新增**：重跑全 ROM 池掃描確認第九輪「無新真實文字池」的結論仍成立（負面結果，未強行擴大語料）；直接像素判讀（非 OCR）category-0 主表 char_idx 151 之後從未檢視過的 punctuation／Latin 區塊，用形狀＋真實語料庫上下文雙重交叉核對新增 7 個符號身分（`、`／`。`／`―`／`！`／`？`／`Ｐ`／`Ｕ`，`PUNCT_LATIN_CHAR_IDX`，見 README「第十四輪偵察」），其中「Ｐ」「Ｕ」由 13 筆真實記錄的「…力ＵＰ」（RPG 屬性提升訊息）交叉驗證。零佔位符記錄 29→41（13.3%→18.5%），`unmapped_glyph` 佔位符 837→688（↓17.8%）。怪物名稱表前綴之謎本輪調查但未解出（結構已釐清，語意仍不明，見 README），維持既有翻譯迴避策略。

## 里程碑 2：可審核翻譯資料（帳本方案）

- [x] 用 `core/ledger/restore_translations.rb` 從空帳本＋本機原文表產生第一批 `work/*.jsonl` 工作記錄。**第十二輪完成**：本遊戲第一批沒有既有帳本可用，改依 skill 指示直接從原文表手動組出工作記錄（`games/shining-soul-1/work/ui-strings-first-batch.jsonl`，本機、不進 Git），8 筆全部 `status: untranslated` 起手後手動填入譯文。
- [ ] 建立人名、地名、技能、道具、戰鬥用語的簡繁術語表。**尚未建立獨立術語表檔案**，第十二輪批次僅在各記錄自帶的 `terms` 欄位裡零星記了幾個（道具／狀態／進階模式／劍士），量太小還不足以抽成正式術語表，留給下一個較大批次。
- [ ] 逐條保存譯文來源、審核狀態、寬度預算及控制碼完整性；控制碼慣例（是否沿用黃金太陽的大寫 `{HH}` 或本遊戲自訂格式）待文字系統解出後再定義。**第十二輪批次全部是無控制碼的短句／單詞，未觸及這個問題**，控制碼慣例仍待下一個含控制碼的批次時再定義。
- [x] 用 `core/ledger/strip_translations.rb` 產生可提交的 `games/shining-soul-1/translations/*.jsonl` 帳本記錄——**不得**帶有 `source` 欄位，`scripts/check-repository-safety.rb` 會擋下違規記錄。**第十二輪完成**：`games/shining-soul-1/translations/ui-strings-first-batch.jsonl`（8 筆，UI／選單短句），`scripts/check-repository-safety.rb` 與 `core/ledger/test/ledger_codec_test.rb` 的 `restore(strip(x))==x` 往返不變量皆已核對通過，這是本遊戲第一筆可提交的翻譯帳本記錄。**第十三輪新增第二批**：`games/shining-soul-1/translations/battle-status-batch.jsonl`（2 筆，第十三輪 OCR 新解出漢字組成的乾淨戰鬥數值訊息「防御力が上がる」／「防御力を上げる」），同樣通過 schema 驗證、`restore(strip(x))==x` 往返核對、既有 ledger codec 測試與 `check-repository-safety.rb`（359 個可見檔案全數通過）。**第十四輪新增第三、四批**：`games/shining-soul-1/translations/npc-dialogue-batch2.jsonl`（10 筆，NPC 對話短句／反應詞／道別句，含一句怪物吼叫擬聲詞）與 `games/shining-soul-1/translations/item-system-batch.jsonl`（3 筆，「を手に入れた」尾段模板片段×2＋道具已滿提示句，`review_notes` 明確記錄尾段模板的語序／控制碼問題尚未解出，不假裝已解決），皆通過同一套驗證流程（schema、往返、ledger codec test、repository safety，361 個可見檔案全數通過）。

## 里程碑 3：完整構建與 QA

- [~] 建立遊戲專屬編碼器／字庫生成／回插工具（`games/shining-soul-1/tools/`）。**第十五輪
  完成 proof of concept**：`tools/build_cn_glyph_poc.py`（本遊戲工具集第一支寫入 ROM 檔案
  的工具）證實整條「插入新中文字形→重寫字串代碼→在 mGBA 實際渲染出來」的機制可行——對五張
  已知字形表的可定址範圍（index 0–254）做全零掃描，找到唯一有實用規模的空位（category 4
  index 40–254，215 格）；用 GNU Unifont 16×16 CJK 點陣（與本遊戲字形槽格式 1:1 吻合，
  免縮放）插入「道」「具」兩個新字；把職業選擇畫面「職業を選んでください」（10 字）改寫成
  `translations/ui-strings-first-batch.jsonl` 既有已翻譯記錄的「道具」（2 字），mGBA 即時
  渲染確認正確顯示、相鄰字串與畫面其餘元素完全未受影響，整份 8 MiB ROM 只改動 115 bytes。
  見 `games/shining-soul-1/README.md`「第十五輪偵察」。**尚未做到（明確留給下一輪，見
  README 該節「可規模化設計需要什麼」）**：這是驗證機制用的一次性腳本，非通用編碼器——215 格
  空位遠不足以承載一整套翻譯的漢字集，需要先解出 IWRAM category 查表（`0x030065f0`，
  category 5–15 目前恆為 NULL）的開機初始化程式碼位置，才能把新字形表接上 category 5–15
  （最多再開放 2,805 格）；也還沒有系統化的「翻譯批次→相異漢字集合→槽位分配」流程，以及
  字串變長（而非本輪示範的縮短）時、在「沒有指標表、字串池位置固定」這款遊戲設計下要怎麼安置
  的通用解法。
- [x] **第二十輪完成容量擴充機制**：覆核並修正第十六輪遺留、從未驗證的 category 5 補丁
  （`tools/build_cn_glyph_category5_poc.py`）。第十六輪的靜態逆向全部正確（type-8 資源標頭
  `0x0846932c`、註冊表字組 `0x080fa510` 為唯一路徑、struct 等差級數，皆獨立重驗吻合），但
  補丁只寫了 category struct 的首字組、其餘 6,172 bytes 留在 `0xFF`，導致畫到 category 5
  的那個畫面 OBJ 圖層整片壞掉（兩次乾淨重跑皆重現，對照基準 ROM 同步驟正常）。修正為整段
  照抄既有的 6,176-byte struct 前綴後，實機渲染確認職業選擇畫面正確顯示中文「字型」、
  sprite 數量精確符合預測（15→7）、既有五類與相鄰字串完全不受影響。**容量上限由 215 格
  提升到每類 256 格 × 11 個未用 category ＝ 2,816 格**。見 `SESSION-LOG.md` 第二十輪。
- [ ] **下一步**：把 POC 變成通用編碼器——「翻譯批次→相異漢字集合→category/槽位分配→
  字形點陣插入→字串代碼重寫」的系統化流程，以及字串變長時的安置解法（仍未解）。
  **開工前必須先處理的已知未知**：新 category 的 struct 前綴是整段照抄 category 0 的，
  意即那串「每 3 個字組一筆」的逐字形中繼資料，其實是 category 0 假名的中繼資料被套用在
  我們塞進去的漢字上。第二十輪測的兩個全形 16×16 字形渲染正常，但**這 3 個字組實際編碼
  什麼（寬度？tile 排列？間距？）並未解出**。在大量配置槽位之前，必須先解出或至少用實驗
  界定這段中繼資料的語意——否則可能在幾百個字形都插好之後才發現排版錯誤。
- [ ] 從乾淨日版 ROM 生成 BPS 並驗證套用後雜湊；重新抽取比對未修改內容是否一致。
- [ ] 在 mGBA 完成核心場景回歸；記錄未測試畫面而非假設成功。
- [ ] 分別發布簡體與繁體 BPS；不發布 ROM。

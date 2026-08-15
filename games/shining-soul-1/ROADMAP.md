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

## 里程碑 1：文字系統與可逆試補丁

- [x] 反組譯覆核 BIOS 解壓縮呼叫候選——結論是全部候選都無法確認為真指令，「文字經 BIOS 常式解壓縮」目前沒有直接證據（但也未被排除，需要更完整的控制流重建才能真正排除）。
- [~] 找到字型／字形點陣資料——**部分完成，第七輪有重大新推進**：OBJ 字型（title／模式選擇畫面，`0x62AA44`–`0x62B8E4`）位置與可重用性第二、三輪已確認（見上）。**第四輪新增**：找到並完整確認了第二張、獨立的 BG 字型表本體——ROM `0x1398e8`–`0x1418e8`（1024 格、`0x8000` bytes），存檔選擇畫面的 BG2／BG3 內容經窮舉逐格比對，與這整段 ROM 範圍逐位元組完全相同，涵蓋 tile-number 欄位能定址的全部範圍；tile-index 直接對應表內位址，這條渲染路徑上不存在需要另外尋找的間接 codepage 層。**第七輪新增**：找到並確認第四張、規模最大的字型表——ROM `0x46abe4` 起，`index*0x80` 線性定址，涵蓋平假名／片假名／Latin／數字／符號（至少 260 格），是職業選擇畫面完整句子「職業を選んでください」的字形來源，7 點零自由參數驗證，並用即時追蹤確認了完整的單字元繪製呼叫鏈（BIOS `CpuSet`/`CpuFastSet`→共用 enqueue 函式 `0x08001154`→唯一呼叫點 `0x080034d0` 的共用 sprite 繪製迴圈），見 `games/shining-soul-1/research/obj-sentence-glyph-loader.md`。四張表（OBJ 標題、BG×2、OBJ 主表）位置皆不同、彼此獨立，對話文字用哪一套仍未知；漢字的定址機制仍未解（不套用主表的 `index*0x80` 公式）。
- [~] 建立 provisional 碼表——**第四輪已建立部分**：直接反查存檔選擇畫面 BG2／BG3 tilemap tile-index，取得約 32 個相異字符的 confirmed／中信心／低信心分級碼表，見 `games/shining-soul-1/research/bg-fonttable-codepage-partial.md`。**第五輪大幅擴充**：姓名輸入畫面的標準五十音鍵盤版面一次核對出 71 個高信心平假名字符（見 `games/shining-soul-1/research/name-entry-hiragana-codepage.md`），總計兩張 BG 表加起來已有 100+ 個相異字符的 confirmed／中信心分級碼表，但**分屬兩張不同的 ROM 表**，尚未合併成單一系統碼表（因為 tile-index 本身不是全域穩定的，同一數字在不同表代表不同字符，見第五輪「重大結構修正」）。**第七輪新增**：OBJ 主表（`0x46abe4`）額外貢獻約 260 個相異字符（平假名／片假名／Latin／數字／符號），是目前規模最大的一張，但同樣是獨立於前兩張 BG 表的第三套碼表，尚未合併。OCR 路線目前仍判斷不需要，因為已知文字＋直接讀 tilemap／算式反推比 OCR 更精確。
- [ ] 定位字串數量、分段方式與（若存在）指標表結構，寫出本遊戲專屬的抽取器——**第七輪部分推進**：已找到「哪個字元代碼對應哪個字形位址」的算式（`0x46abe4+index*0x80`）與「誰把字形搬進 VRAM」的完整呼叫鏈，但**尚未找到句子本身的字元代碼序列存在 ROM 何處**（多種假設已測試為負面結果，見 `research/obj-sentence-glyph-loader.md`），仍是本項目未完成的核心缺口。
- [ ] 建立本機原文表 `research/shining-soul-1-decoded.jsonl`（`{"string_id", "locale", "text", "provenance"}`），供 `core/ledger/restore_translations.rb` 使用。

## 里程碑 2：可審核翻譯資料（帳本方案）

- [ ] 用 `core/ledger/restore_translations.rb` 從空帳本＋本機原文表產生第一批 `work/*.jsonl` 工作記錄。
- [ ] 建立人名、地名、技能、道具、戰鬥用語的簡繁術語表。
- [ ] 逐條保存譯文來源、審核狀態、寬度預算及控制碼完整性；控制碼慣例（是否沿用黃金太陽的大寫 `{HH}` 或本遊戲自訂格式）待文字系統解出後再定義。
- [ ] 用 `core/ledger/strip_translations.rb` 產生可提交的 `games/shining-soul-1/translations/*.jsonl` 帳本記錄——**不得**帶有 `source` 欄位，`scripts/check-repository-safety.rb` 會擋下違規記錄。

## 里程碑 3：完整構建與 QA

- [ ] 建立遊戲專屬編碼器／字庫生成／回插工具（`games/shining-soul-1/tools/`）。
- [ ] 從乾淨日版 ROM 生成 BPS 並驗證套用後雜湊；重新抽取比對未修改內容是否一致。
- [ ] 在 mGBA 完成核心場景回歸；記錄未測試畫面而非假設成功。
- [ ] 分別發布簡體與繁體 BPS；不發布 ROM。

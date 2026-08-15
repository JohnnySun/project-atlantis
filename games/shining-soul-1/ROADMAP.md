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
- [ ] **尚未開始**：字元代碼→字形 tile 索引對照表（codepage）——本輪判斷最快路徑是直接反查存檔選擇畫面 BG2／BG3 tilemap 的 tile-index 陣列（已知會顯示什麼文字），而非繼續往上追字型傳輸佇列的呼叫鏈，留給下一輪。

## 里程碑 1：文字系統與可逆試補丁

- [x] 反組譯覆核 BIOS 解壓縮呼叫候選——結論是全部候選都無法確認為真指令，「文字經 BIOS 常式解壓縮」目前沒有直接證據（但也未被排除，需要更完整的控制流重建才能真正排除）。
- [~] 找到字型／字形點陣資料——**部分完成，第三輪有推進**：已確認 title 畫面「シャイニング・ソウル／PUSH START」用的 OBJ 字形資料格式（4bpp／32 bytes/tile）與 ROM 位置（約 `0x62AA44`–`0x62B8E4`，逐位元組原封不動搬移，非 BIOS 壓縮），且已在模式選擇畫面看到**同一套機制載入的第二組不同字符**（片假名選單文字），確認這是可重用字型系統而非單一畫面的專屬美術資源。搬移機制本身（真實 `swi` BIOS CpuSet／CpuFastSet 呼叫＋通用傳輸佇列 flush 迴圈，ROM file offset 約 `0x11a0`–`0x11fe`）已定位；但「哪段程式碼決定要把哪個字元排進佇列」（真正的字型載入器決策點／codepage 前置邏輯）**仍未定位**，一個候選推入函式已測試否定。
- [ ] 建立 provisional 碼表或改用渲染+OCR 路線（視文字系統形狀而定，尚無法判斷哪種更適合）——第三輪已找到三個獨立的動態文字畫面（標題、模式選擇、存檔選擇），下一輪可直接從存檔選擇畫面的 BG tilemap tile-index 反查碼表，不必再等更多畫面。
- [ ] 定位字串數量、分段方式與（若存在）指標表結構，寫出本遊戲專屬的抽取器。
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

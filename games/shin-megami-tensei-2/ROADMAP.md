# 《真・女神轉生 II》路線圖

## M0：身分、範圍與唯讀基準

- [x] 建立獨立 slug `games/shin-megami-tensei-2/`，不混入其他遊戲資料。
- [x] 記錄 A5TJ header、ROM size、CRC32、MD5、SHA-256 與 header complement 差異；不修補原 ROM。
- [x] 建立不輸出完整原文的 `tools/recon_static.py`。
- [x] 使用本 session 專用的 2367 headless GDB 做一次有界輸入／VRAM／OAM 回合。
- [x] 依 GBA 標準 VRAM、OBJ palette、OAM 與 4bpp/1D mapping 假設完成畫面級交叉驗證：Start 後可渲染出遊戲內日文免責文字。

## M1：文字消費者與格式偵察

- [x] 以 `Z3,04000130,2` 讀取 watchpoint 確認 KEYINPUT 的執行期消費點（PC `0x080a9a0a`），並以 active-low 值完成一次 Start 狀態轉換。
- [x] 記錄新畫面的 `DISPCNT`、BG 設定、VRAM/OAM 非零統計、OBJ tile 範圍與 46 個 active sprite 的可重現證據。
- [x] 確認至少一個實際文字消費結果：OBJ sprite 合成影像中出現三行日文免責文字。
- [~] 找到文字的實際儲存形式、字元代碼與 codepage；目前只有畫面消費證據，沒有把影像反推成原文表。
- [ ] 確認字串池／指標／bank、壓縮、換行與控制碼；不套用 SMT I、黃金太陽或其他遊戲格式。
- [ ] 分別定位惡魔、技能、道具、系統與劇情資料，並建立本作 decoder 及本機 `research/*-decoded.jsonl`。
- [ ] 以未修改資料重新抽取驗證可逆回插路徑。

## M2：可審核翻譯 ledger

- [ ] 先完成日文 source table 與 stable string ID，再建立第一個有限 UI／事件批次。
- [ ] 專有名詞先查 Wikipedia zh-tw、巴哈姆特及其他獨立社群來源，建立 `zh-TW` 術語表與來源紀錄。
- [ ] 以 `restore_translations.rb` 產生本機工作記錄，保留來源 hash、控制碼與寬度預算。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的提交 ledger，通過 schema 與 repository safety 檢查。

## M3：回插與 QA

- [ ] 建立本作專用 encoder、字庫與回插器。
- [ ] clean ROM → 重建 ROM → 重新抽取，確認未修改內容一致。
- [ ] 產生／套用 BPS 並完成 byte-for-byte round trip。
- [ ] 在 mGBA 驗證已翻譯場景；未測畫面、字寬、控制碼與存檔風險都要明列。

# 《勇者鬥惡龍怪獸篇 旅團之心》路線圖

## M0：基準與唯讀偵察

- [x] 建立遊戲專屬目錄、`game.yml`、README、工作帳本邊界。
- [x] 確認 GBA 標頭：`A9HJ`、Rev.00、`DQM-CARAVANH`、header complement。
- [x] 審核公開 clean ROM 指紋與目前本機候選的差異。
- [x] 建立不輸出完整原文的 `tools/recon_rom.py`。
- [x] 以獨立 GDB 埠在 clean A9HJ 驗證 mGBA ROM 入口、VRAM watchpoint 與開機 live layout；candidate 結果只作歷史對照。
- [x] 取得／核准 clean 日版 ROM，重新建立基準指紋。

## M1：文字與字型系統

- [ ] 找到文本的儲存形式：固定表、腳本 bytecode、壓縮 blob 或執行期生成資料。
- [ ] 找到文本消費者、字型搬移與實際螢幕渲染路徑。
- [ ] 追蹤 title／menu／事件畫面，區分 tile、bitmap、sprite 與可能的 VWF 路徑。
- [ ] 確認指標／bank／壓縮格式與控制碼，不套用其他遊戲假設。
- [ ] 建立可重跑的 `research/*-decoded.jsonl` 本機原文表。
- [ ] 分別記錄 glyph addressing 與 glyph identity 的證據層級。

## M2：帳本與有限翻譯

- [ ] 建立 `translations/glossary.zh-TW.tsv`；怪物、技能、道具、人名與地名先查 Wikipedia zh-tw、巴哈姆特及其他獨立社群來源。
- [ ] 以一個可達 UI／事件建立第一批本機 `work/*.jsonl`。
- [ ] 保留 `zh-Hans`／`zh-TW`、狀態、術語、控制碼與寬度預算。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的 ledger，通過 schema／安全檢查。

## M3：回插與發布前 QA

- [ ] 建立遊戲專用 encoder、字庫與回插器。
- [ ] clean ROM → 重建 ROM → 重新抽取，確認未修改內容一致。
- [ ] 產生並套用 BPS，完成逐位元組 round-trip。
- [ ] 在 mGBA 及可用實機完成已覆蓋場景 QA，記錄未測畫面與剩餘風險。

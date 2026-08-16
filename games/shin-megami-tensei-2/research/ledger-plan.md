# 本作可逆 ledger 邊界

目前沒有建立任何翻譯記錄。這是刻意的安全邊界：A5TJ 的文字 source table、stable string ID、codepage 與控制碼尚未被證明，現在填入日文或中文會把畫面觀察誤當成可抽取原文。

後續流程固定如下：

1. decoder 只讀取本機 ROM，輸出 `research/shin-megami-tensei-2-decoded.jsonl`；該檔案由 repository ignore 規則隔離，不提交完整原文。
2. 對一個有明確畫面上下文的有限批次，以 `core/ledger/restore_translations.rb` 產生本機 `work/*.jsonl`，每筆保留 `source_locale: ja-JP`、`source_hash`、ID、控制碼狀態、寬度預算與術語來源。
3. 翻譯完成並經 `zh-TW` 審核後，以 `core/ledger/strip_translations.rb` 產生 `translations/*.jsonl`；提交格式不得含 `source` 欄位。
4. 每批次都要通過 ledger schema、codec round trip、repository safety 與本作 decoder 重新抽取比對。

專有名詞在第一批真正開始前，依 `AGENTS.md` 至少交叉查 Wikipedia zh-tw、巴哈姆特及另一個獨立社群來源；來源分歧時保留現有共識或明列未決，不自行創造譯名。

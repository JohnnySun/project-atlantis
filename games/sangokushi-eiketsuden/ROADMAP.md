# 路線圖

## 里程碑 0：工作區與公開術語基線

- [x] 建立獨立 slug `games/sangokushi-eiketsuden/`，只涵蓋《三國志英傑伝》；不建立《孔明傳》資料。
- [x] 記錄公開產品代碼候選 `B3EJ`，並和 GBA ROM header game code 分欄；後者仍待日版 dump 驗證。
- [x] 閱讀 Project Atlantis 的 ledger 規範，建立 `research/`、`work/`、`translations/` 的原文隔離邊界。
- [x] 以中文 Wikipedia、巴哈姆特、光榮官方攻略書頁和日文 GBA 攻略 Wiki 交叉建立 `zh-TW` 術語候選。
- [ ] 取得可合法使用的日版 B3EJ ROM；目前本機沒有候選檔，header／CRC／雜湊均未驗證。

## 里程碑 1：ROM 身分與唯讀資料偵察

- [ ] 解析 header title、game code、maker code、revision、大小與補數校驗。
- [ ] 記錄 CRC32、MD5、SHA-1、SHA-256；確認是否為 B3EJ 版本以及是否存在 revision 差異。
- [ ] 掃描標準 Shift-JIS、候選指標表、GBA 位址指標、BIOS 解壓縮呼叫和高熵／填充區段。
- [ ] 建立並保存失敗候選：資料偏移、測試條件、否定理由和是否需要執行期重測。

## 里程碑 2：文本、字型與可逆路徑

- [ ] 定位劇情、武將／地名、官職／兵種、策略、戰役事件和 UI 文本的實際資料區。
- [ ] 分別確認字串結構、終止符、指標／池、壓縮、控制碼、換行和字型／glyph addressing。
- [ ] 以已知畫面或執行期渲染交叉驗證 codepage；分開記錄 glyph pool 定位和 Unicode 身分確認。
- [ ] 寫出 `games/sangokushi-eiketsuden/tools/` 下的唯讀 decoder／renderer，輸出本機原文表。
- [ ] 只有在未修改內容可抽出再回插後逐 byte 一致，才宣稱回插路徑可行。

## 里程碑 3：有限量翻譯與 ledger

- [ ] 從一個可達且結構完整的短批次開始，不先翻整部遊戲。
- [ ] 以 `restore_translations.rb` 產生本機 `work/*.jsonl`，保留來源 hash、上下文、譯文狀態和術語引用。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的提交帳本；通過 schema 與 `check-repository-safety.rb`。
- [ ] 先完成劇情／戰役事件小批次，再擴充武將、地名、官職、策略和道具；每批次記錄 string ID 集合。

## 里程碑 4：構建、BPS 與執行期 QA

- [ ] 建立遊戲專用 encoder、字庫子集和嚴格的字寬／行數／控制碼檢查。
- [ ] 從 clean ROM 建立 ROM、BPS，套用 BPS 後做 byte-for-byte round trip，並重新抽取比對。
- [ ] 在 mGBA 驗證已翻譯的核心場景、戰役事件和選單；未測畫面必須明確列出。
- [ ] 在所有必要 QA 通過前，維持 `status: research`，不發布 ROM，只發布可合法使用者套用的 patch。

## 接受條件

- ROM 身分：header／產品候選／版本／大小／四種雜湊都有明確證據，沒有把 B3EJ 型號直接當 header code。
- 文本解碼：同一字串可由 decoder 穩定抽出，原文表可通過 ledger restore，且抽出結果能以已知畫面或獨立資料交叉核對。
- 回插路徑：未翻譯資料回插後重新抽取與原文表一致，指標／壓縮／控制碼／字型覆蓋檢查全部通過。
- 翻譯批次：只提交 ledger，不提交原文；每批次有 string ID、術語版本、QA 結果與剩餘風險。

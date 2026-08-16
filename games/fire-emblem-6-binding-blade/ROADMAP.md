# FE6（AFEJ）工作路線

## M0：可審核骨架

- [x] 建立遊戲專屬 `README.md`、`ROADMAP.md`、`game.yml`。
- [x] 建立 ledger／work 分離規則與提交邊界。
- [x] 建立只讀 ROM 身分／結構偵察入口。
- [x] 建立初步 zh-TW 術語表；未經 ROM 語境核對的項目保留 provisional 標記。

## M1：日版 ROM 與文字系統

- [ ] 讀取合法 AFEJ ROM，確認標頭、game code、maker code、revision、CRC32 與 SHA-256。
- [ ] 定位劇情、支援、章節事件、單位／武器／技能、商店／戰鬥／系統訊息及圖像文字。
- [ ] 確認文本資料結構：字元寬度、終止／換行／選項／名字／數字控制碼、指標與壓縮。
- [ ] 確認各字型池的地址／stride 與 Unicode 身分；分開記錄「已定位」和「已辨識」。
- [ ] 寫出嚴格解碼器，產生被忽略的 `research/afej-decoded.jsonl`。
- [ ] 為負面結果與假陽性建立可重跑的研究紀錄，不把猜測寫成結論。

## M2：有限量翻譯批次

- [ ] 從一個可閉合的小批次開始（優先選單／系統訊息或一個完整場景）。
- [ ] 以 `restore_translations.rb` 產生 `work/` 工作記錄，明確填寫 `zh-Hans` 與 `zh-TW`。
- [ ] 完成翻譯、術語、字寬／行數、控制碼與 codepage 覆蓋檢查。
- [ ] 以 `strip_translations.rb` 產生不含原文的 `translations/*.jsonl` ledger。

## M3：可逆構建與 QA

- [ ] 建立 FE6 專屬字型、編碼、文本回插與擴容工具。
- [ ] 從乾淨 AFEJ ROM 生成測試 ROM，重新抽取並核對未修改內容。
- [ ] 建立 BPS 套用 round-trip 與目標雜湊紀錄。
- [ ] 在 mGBA 覆蓋標題、主選單、序章／早期章節、支援、戰鬥、結局與圖像文字；未測項目明列。

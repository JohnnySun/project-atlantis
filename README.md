# Project Atlantis

一個以可重現工程為核心的 **AI 輔助 Game Boy Advance 本地化計畫**。目標是把遊戲文字抽取、簡繁翻譯、術語管理、中文字庫、排版檢查、ROM 回插和實機驗證整理成可重用流程，而不是為每款遊戲從零開始。

名稱取自 Nintendo 在 1990 年代研究的 32-bit Game Boy 後繼機 **Project Atlantis**。它不是後來 GBA 的正式開發代號，但可視為相關技術探索的前身；這裡借用「被重新發掘的掌機計畫」作為工程意象。

《黃金太陽 開啟的封印》是第一個試驗項目，用來驗證既有漢化審計、自訂中文字碼逆向，以及簡體／繁體雙版本共用資料模型。

## 核心原則

- **原案優先**：保存使用者提供的原文及版本來源，AI 只產生可審核的候選譯文。
- **簡繁並行**：`zh-Hans` 和 `zh-Hant` 是兩個可獨立修訂的語種，不做不可追蹤的一鍵機械轉換。
- **字庫可重用**：共用字形來源、授權、缺字清單與生成方法；每款遊戲只保存其子集與映射。
- **可回溯**：每條譯文都能追蹤原文、譯者／模型、術語決策、審核狀態和遊戲內位置。
- **可重現**：只由使用者本機的合法 ROM 和公開工具構建；倉庫不保存或發布商業 ROM。
- **證據驅動 QA**：錯譯、溢出和程式問題都需要字串 ID、場景、重現步驟及修復前後結果。

## 倉庫結構

```text
core/                         通用抽取、轉換、字庫、QA、構建介面
locales/                      簡體與繁體的共用規則、字形和術語層
games/                        各遊戲的 manifest、工具、研究與譯文
  golden-sun-the-broken-seal/ 第一個試驗項目
docs/                         架構、資料格式、工作流與合規邊界
schemas/                      原案、譯文與審核狀態的機器可驗證格式
examples/                     不含商業遊戲文本的最小示例
scripts/                      倉庫安全及自動化檢查
vendor/fonts/                 經授權、固定版本且附來源記錄的第三方字庫
```

## 第一階段

1. 完成《黃金太陽》自訂中文字碼及字庫映射。
2. 定義不綁定遊戲的字串交換格式。
3. 建立原文、`zh-Hans`、`zh-Hant`、術語和 QA 狀態的資料管線。
4. 產生兩套最小字庫，檢查缺字、寬度與 VRAM／ROM 預算。
5. 從乾淨 ROM 可重現地輸出測試構建與 BPS，並在模擬器和實機驗證。

詳見 [計畫章程](docs/PROJECT_CHARTER.md)、[工作管線](docs/PIPELINE.md)及[黃金太陽項目](games/golden-sun-the-broken-seal/README.md)。

原案的第一版交換格式是 [localization-record.schema.json](schemas/localization-record.schema.json)，示例見 [localization-records.jsonl](examples/localization-records.jsonl)。

## 版權與資料邊界

本倉庫只保存自行編寫的工具、規格、研究筆記、允許分享的翻譯資料，以及經授權且完整標明來源的開源字庫。ROM、存檔、上游補丁、設備備份、未經授權的大段遊戲文本及來源不明的第三方字型不進 Git。提交前執行：

```sh
ruby scripts/check-repository-safety.rb
```

目前是私人研究計畫；程式碼及資料的公開授權會在來源與字型授權完成審核後另行決定。

# Core

此目錄將承載與特定遊戲無關的能力：

- 本地化記錄 schema 與驗證器
- 術語及翻譯記憶管理
- 簡繁差異與混用檢查
- 點陣字庫子集、缺字與授權報告
- 控制碼保真、行寬和溢出 QA
- 可重現構建及測試報告介面

遊戲的指標、壓縮、碼頁和補丁地址不得直接寫入 core；它們由 `games/<game>/` 的 adapter 提供。

`patches/bps_create.rb` 與 `patches/bps_apply.rb` 提供不綁定遊戲的 BPS1 產生與套用工具。產生器輸出 `SourceRead`／`TargetRead`，套用器支援 BPS1 的四種 action，並驗證 source、target 與 patch CRC32。

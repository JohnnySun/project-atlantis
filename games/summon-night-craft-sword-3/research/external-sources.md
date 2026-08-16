# B3CJ 外部工程資料固定紀錄

本文件只固定公開資料的版本、來源與授權狀態，不複製第三方原始碼、完整腳本、ROM 或字型。

## 固定版本

| 資料 | 固定版本／位置 | 用途 | 授權／保存界線 |
| --- | --- | --- | --- |
| Data Crystal 遊戲頁 | [oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650) | B3CJ、容量、CRC32、header metadata 交叉比對 | 依 [Data Crystal Community](https://datacrystal.tcrf.net/wiki/Data_Crystal/Community) 頁面所述，站內 code/information 以 GFDL 為基礎；本專案只引用 metadata 與研究結論 |
| Data Crystal TBL | [oldid=53006](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006) | 日文 code-table 線索與本機 raw byte 解碼交叉比對 | 不把頁面表格整份匯入 Git；只記錄與本機 ROM 相符的格式結論 |
| csm3 | [commit `7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2`](https://github.com/jiangzhengwenjz/csm3/commit/7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2) | 指標解析、LZ77 callsite、PSI3 script consumer 的控制流／資料結構線索 | 固定 commit 根目錄未找到 LICENSE/COPYING/NOTICE；只作 review reference，不重發布其 source 或資產 |

固定日：2026-08-16。Data Crystal 的頁面版本以 oldid 固定；本輪 shell raw fetch 對 TBL oldid 回應 HTTP 403，因此沒有把未驗證的 HTML 快取到工作區。頁面 URL、oldid 與可核對的本機交叉結果仍保留在本紀錄。

## csm3 唯讀 review 收據

第三方 checkout 只存在於 `/private/tmp/csm3-review-b3cj`，沒有複製到遊戲目錄或 Git。固定 commit 的 `csm3.sha1` 為 `3f5253fcf57e07ce52472bd29a61d16b98a12376`，與本機 B3CJ ROM 的 SHA-1 完全一致；這是版本身分交叉證據，不代表把反編譯結果當成 ROM 原文。

本輪實際閱讀的線索：

- `src/main.c:480-505`：`sub_08001D0C` 初始化 resource base，`sub_08001D3C`／`sub_08001D78` 以 `int` pointer table 解析 resource，故每個 relative unit 的資料步長是 16 bytes。
- `src/script.c:51-63`：`sub_08012D30` 由 type-2 resource 取資料並呼叫 `LZ77UnCompWram`。
- `src/script.c:78-88`：`sub_08012E14` 將解壓資料的 `+0x10` 作為 stream base，按 little-endian halfword 消費。
- `src/script.c:203-251` 與 `asm/code_080123E4.s`：script VM 的 command dispatch 與 `sub_080127E4` consumer；這些 table 是 VM dispatch，不被誤標成文字指標表。

這些行號只保存可重複的 callsite 索引；csm3 的完整 source 不屬於本作提交內容。

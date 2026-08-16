# 《世界傳說：換裝迷宮 3》研究路線圖

## M0：身分與邊界

- [x] 以 GBA header、game code、maker code、大小、header complement、CRC32 鎖定 B3TJ
- [x] 以多個公開資料來源交叉核對日本版身分
- [x] 建立本遊戲專屬工具、測試與研究文件邊界
- [x] 確認 ROM、sav、本機原文表不進 Git

## M1：只讀格式偵察

- [x] 建立第一 pass 結構掃描器，將 Shift-JIS、指標與壓縮簽章標成候選而非結論
- [x] 限定五個明確資料窗，建立嚴格 NUL／Shift-JIS 本機抽取器
- [x] 測試非法位元組、未終止記錄、控制碼保留與 GBA 絕對指標計數
- [x] 完成一個有界 mGBA GDB runtime 回合，確認部分 BIOS 解壓縮 wrapper 的實際呼叫
- [x] 把 runtime 證據、輸入導覽失敗界線與假設寫入研究報告

## M2：尚未開始的必要證明

- [ ] 從可重現 breakpoint/watchpoint 找到文字 renderer 的入口與消費者
- [ ] 確認字型 glyph 格式、codepage、寬度表與 glyph 載入路徑
- [ ] 分類事件、角色／服裝／技能、戰鬥與選單各自的指標／控制碼結構
- [ ] 證明每一種字串的容量、指標更新規則、壓縮／未壓縮界線
- [ ] 寫出不超容量即拒絕的回插 builder，完成 bytes→ROM→runtime round-trip
- [ ] 以日本原文建立可審核 ledger；專有名詞先做 Wikipedia zh-tw、巴哈姆特及其他社群交叉查證

## M3：有限翻譯與 QA

- [ ] 只在 M2 證明後建立第一批等長／有餘裕的 zh-TW ledger
- [ ] 覆蓋角色、事件、支線、服裝／技能與戰鬥文字的抽取／回插測試
- [ ] mGBA 逐畫面驗證控制碼、換行、字寬、指標與無亂碼
- [ ] 實際可玩流程回歸後，才評估是否進入翻譯里程碑

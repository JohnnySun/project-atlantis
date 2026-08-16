# FE6（AFEJ）工作路線

## M0：可審核骨架

- [x] 建立遊戲專屬 `README.md`、`ROADMAP.md`、`game.yml`。
- [x] 建立 ledger／work 分離規則與提交邊界。
- [x] 建立只讀 ROM 身分／結構偵察入口。
- [x] 建立初步 zh-TW 術語表；未經 ROM 語境核對的項目保留 provisional 標記。

## M1：日版 ROM 與文字系統

- [x] 讀取合法 AFEJ ROM，確認標頭、game code、maker code、revision、CRC32 與 SHA-256。
- [x] 以 mGBA/GDB 確認一條文字 buffer → 兩位元組碼表 → glyph index → VRAM bitmap composer 路徑。
- [x] M1.5：以可重跑 loader breakpoint、copy-wrapper breakpoint 與 EWRAM write-watchpoint 證明 ROM pointer table → EWRAM code-unit buffer；記錄一個 `0x01` marker 與 payload 後的 `0x00` 邊界。
- [x] M1.6：反組譯實際 loader entry、caller return 區域與 IWRAM worker 的 ROM 初始化來源；確認 `table + index * 4`、bounded table boundary 與 custom tree expansion。
- [x] M1.6：建立 `index 3080..3095` 的 16 筆 opaque code-unit/control corpus；保存 stable ID、pointer provenance、source/output hash、長度與 marker offsets；16/16 decode→encode byte-identical，index 3087 與獨立 runtime receipt hash 相等。
- [x] M1.7：由 `0x08098afc`／`0x08098b10` 的靜態 BL 與 runtime LR 收據證明高階 selector caller → `0x08013ad0`；修正 `0x08013b04` 為 ARM7TDMI 雙半字 Thumb BL 第二 halfword，實際 copy callsite 為 `0x08013b02`。Start 可達第二顯示狀態，但 bounded 觀察未命中同一 loader 或 `0x02029404` write-watchpoint，因此第二場景的內容分類與 table 歸屬維持 unknown。
- [x] M1.8：全 ROM 靜態枚舉 163 個 `BL 0x08013ad0` direct callsites、104 個 bounded caller groups；確認非 selector 候選 `0x080985d8`／`0x080985ec` 的參數／stack index 來源，並以 natural 1 筆 + 明確 controlled 1 筆取得第二 caller 的 table/source→EWRAM receipt。自然導航未命中第二 caller，`0x06014000` 新 sink watchpoint 零命中，內容分類與 `0x01` 控制碼語義維持 unknown/opaque。
- [x] M1.9：以三個 fresh mGBA／單一 GDB connection 完成 `start,a`、`start,a,a,a` 與 bounded menu/chapter 序列的 natural receipts；每條保存按鍵序列、時間窗、display I/O／VRAM hash、`0x080985ec`／`0x08098624`／`0x08098b10`／`0x08013ad0` hit counts。三條皆只重現 index 3087 的 selector caller，且在 `0x08098c24`／`0x08098c78` 觀察到 EWRAM consumer；第二 caller、`0x08099424`／`0x080995b0`／`0x080995a6` writer 與固定 sink 均為 0，留下 `0x080985d8`／`0x08098624` 上游 state/menu gate 作為下一個最小缺口。
- [ ] 定位劇情、支援、章節事件、單位／武器／技能、商店／戰鬥／系統訊息及圖像文字。
- [ ] 確認文本資料結構：字元寬度、終止／換行／選項／名字／數字控制碼、指標與壓縮。
- [ ] 確認各字型池的地址／stride 與 Unicode 身分；分開記錄「已定位」和「已辨識」。
- [ ] 擴大嚴格解碼器至劇情／支援／事件／資料表各內容類別；目前 M1.6 僅覆蓋一個 bounded loader/table cohort，產生的 `research/afej-decoded.jsonl` 仍是 opaque tokens。
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

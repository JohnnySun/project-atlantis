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

## M1.5：文字消費者 bounded proof

- [x] 對五個資料窗做 absolute／relative pointer cross-classification，區分 confirmed 與 provisional
- [x] 選定有 direct pointer table 引用的 concrete record `sjis:0x146EE0`
- [x] 以共用 GDB client 建立可重跑的 KEYINPUT read-watchpoint navigation harness
- [x] 在 bounded early-UI sequence 中驗證 input caller；選定 record read watchpoint 明確記錄為 negative
- [x] 對 baseline BG charbase 做 ROM→VRAM exact byte match，並保留重複 tile／未歸因 glyph 的限制
- [ ] 命中 selected record 的 live consumer，沿 caller 連到 decoder／codepage／glyph VRAM destination

## M1.6：resolver live-edge boundary

- [x] 在 `0x08003444` entry 與 `0x0800345C` return site 記錄 live `r0` table base、`r1` index、resolved `r0` 與 caller LR
- [x] 以五個已確認文字窗及 strict record boundary 自動過濾 resolver return，不把高位資源位址誤升格成文字
- [x] 長度受限 menu／button sequence 共 224 個 KEYINPUT events；resolver 8 hits 均為五窗外資源位址，caller 落在本作 asset-loader callsites
- [x] selected `sjis:0x146EE0` read watchpoint 0 hit；state-table runtime override 只作 navigation negative，不當作正常流程證據
- [ ] 找到 resolver 返回五窗 strict record 的正常遊戲 caller，並以 source read／RAM decoder／glyph destination 建立 text edge

詳情見 [`research/m16-resolver-20260816.md`](research/m16-resolver-20260816.md)。目前仍不可宣稱 codepage、glyph identity、翻譯或回插成立。

## M1.7：state 4 正常導覽邊界

- [x] 在 `0x08005ECC` 與共同 return `0x08005E12` 建立單一 entry／return probe，記錄 next/current/previous bytes、signed dispatch index、table base、resolved function 與 LR
- [x] 靜態確認 boot state 0 以正常 caller 設定 next state 4，以及 state 4 `0x08009C68 → 0x0800A58C → 0x0800A388 → 0x080004EC` 初始化鏈
- [x] 靜態確認 `0x08000E0C` 的 active-low KEYINPUT→`r1`→`0x030033F8` edge path，與 `A1AC` bit 0 對 resource object `+0x54`／`A2C0` return 的正常條件
- [x] 以本作獨立 mGBA 與既有 KEYINPUT harness 重跑 bounded startup；runtime 確認 dispatcher、state 4 handler、`A58C` 與 `A388` caller，未覆寫 state 或 save
- [x] 擴充 `tools/state_probe.py` 的 open-dispatch negative metadata 與 bounded sequence 測試；輸出只含 registers、state、hash、count metadata

M1.7 的完整 static、confirmed/provisional/negative runtime 界線見
[`research/m17-state4-navigation-20260816.md`](research/m17-state4-navigation-20260816.md)。M1.7
本身仍不可宣稱 resolver text edge、decoder、codepage、glyph identity、翻譯或回插成立。

## M1.8：A1AC 單一 register-write 與正常 return

- [x] 在 A030/A050 正常 gate 後，只以一次 `0x03F7` START pulse 離開初始化 loop，並保留有限 `0x03FF` release；不覆寫 state、object 或 save
- [x] 在 live `0x0800A1AC` 後對 KEYINPUT destination `r1` 寫入 active-low `0x03FE`，取得 core GDB `OK` ACK，沿用 packet delay 與一次 timeout retry 邊界
- [x] 觀察 IWRAM `0x030033F8` bit 0，bounded single-step 驗證 `0x0800A174 → 0x0800A180`，並確認 object `0x0200C6DC + 0x54` 由 0 變 1
- [x] 取得 `0x0800A2C0` entry／`r0=1` caller-after、dispatcher common return `0x08005E12`、state 4→7 與固定畫面 hash metadata
- [x] 正常 return 後以 clean mGBA session 重跑 `consumer_probe.py --trace-first-record`：strict count `8938`、4 個 resolver hits 全在五窗外，source read/caller return 均為 0
- [x] 建立 `tools/m18_a1ac_probe.py`、離散測試與不含 raw/source 的 runtime research receipt
- [ ] 沿 state 7 正常畫面找到第一個真正落入五窗 strict record 的 text consumer，再追 RAM decoder／glyph writer

M1.8 的完整 confirmed/provisional/negative/unknown 邊界見
[`research/m18-a1ac-runtime-20260816.md`](research/m18-a1ac-runtime-20260816.md)。目前仍不可宣稱
文字 consumer、codepage、glyph identity、翻譯或回插成立；下一個最小切片是 bounded
state 7 text-consumer trace，不是擴大 pointer scan。

## M2：文字 consumer、碼頁與回插必要證明（進行中）

- [x] 建立不含原文的 8,938 筆 source-hash ledger scaffold 與控制標記 metadata；以
  本機 source table 做 decoder／hash drift verify，所有 target 仍為 untranslated
- [x] 對既有固定 ROM literal 做 bounded layout／width-table metadata verify；只列為
  provisional，不把它升格成字型／codepage 證明
- [x] 對固定 `0x080025CC` parser 做 bounded static contract verify：`%` dispatch、
  84-entry jump table、IWRAM cursor、NUL output 與 width-helper candidate；仍未升格
  成 live source consumer
- [x] 對 parser 的 4 個 direct callsite 做 bounded chain verify；確認
  `0x08001E26→0x08001DBC` 的 IWRAM tilemap writer，以及
  `0x080014F4→0x08001414→0x080DDCC4+index*0x20` 的 glyph source candidate；
  明確保留 IWRAM→VRAM 與 runtime source edge 為 unknown
- [x] 重新驗證既有 `0x0DD1B84–0x0DD1BB4` 12-entry direct table：12/12 strict
  `text-pool` targets 與 selected `sjis:0x146EE0` provenance；容量／類別／rewrite
  規則仍未確認
- [x] 分離固定 caller 發現的 control-only `format:0x1474C0` `%k` template，與
  後面的 `sjis:0x1474C4` strict record；template semantics／runtime read／ledger
  pairing 仍未確認
- [x] 固定驗證 `0x08004D90` 的 2 個 direct callsite 與 5 個 ROM lookup pointer
  slots；只升格為 static codepoint-lookup，保留完整 codepage／glyph／字寬為
  provisional 或 unknown
- [x] 固定驗證 `0x08001414` 的 `0x20`-byte asset stride、parity transform 與
  `0x03001464` 的 2-bit lookup expansion shape；只升格為 static font-pipeline
  contract，保留 live glyph、完整 codepage、字寬與 VRAM edge 為 unknown
- [x] 建立只針對 `0x08001414` 的 bounded font consumer harness；只保留
  `r2→asset read→transform→scratch write` metadata，未把 harness 產物冒充
  runtime hit
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

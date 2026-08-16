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
- [x] M1.10：以既有 strict tree worker census 全部 3342 pointer entries；3203 筆 decode→encode 與 source-span byte-identical，139 筆明確記為 `decoder_buffer_limit_no_terminator`（首筆 index 17）。提交的 `research/m110-table-census.json` 僅存 hash／provenance／長度／marker counts；`0x01`／`0x04`／`0xff` 仍 opaque，139 筆 worker/格式缺口與內容分類不猜測。
- [x] M1.11：建立可重跑的 static gate report：全 ROM 163 個 loader direct BL、`0x080985d8` 的 10 個 direct callers、`0x08098624` 的 1 個 direct caller、selector 對照的 8 個 direct callers；另以對齊 Thumb function-pointer 搜尋記錄 `0x08098341`（file `0x691230`）與 `0x080984a9`（file `0x691358`）的 dispatch-like 鄰接 word。這只證明 callback／資料表候選，不宣稱自然 reachability、場景分類或 codepage。
- [x] M1.12：fresh mGBA／單一 GDB connection 的 bounded natural route 同時重現 selector index 3087 與另一個 direct caller `0x08009252` 的 index 2678、2679；三筆都經 `0x08013ad0` → pointer table → `0x02029404`，保存 source-window/output hash 與 marker offsets。`0x08691230`／`0x08691358` read-watchpoint 與 `0x08098340`／`0x080984a8` callback entry 均 0，第二 caller 已確認但場景分類與 callback dispatch 語義仍 unknown/opaque。
- [x] M1.13：由 static BL census 證明 `0x080117ba` → `0x08009240` → `0x08009252` 的兩層 generic loader chain（wrapper target 共 6 個 direct callsites）；fresh route 的 `0x08009240` LR `0x080117bf` 可回推 `0x080117ba`，loader LR `0x08009257` 可回推 `0x08009252`。同一路徑 renderer branch `0x08098f68/0x08098f78/0x08099424/0x08099460/0x080995b0/0x08099580/0x080995a6` 全 0，維持 text-consumer-only negative，不提升 `0x01` 或內容分類。
- [x] M1.14：沿 `0x0800e02a` 的 static `BL 0x0809df14`／共用 `BX r1` thunk，確認 dispatch table `0x085c4164 + index*8`；index 86 的 entry `0x085c4414` 儲存 Thumb pointer `0x08011779`／flag `0x00000002`。natural route 取得 13 次 dispatch callsite，其中 2 次 `r1=0x08011779` 並各自進入 `0x08011778`；candidate pointer read-watch 0、renderer branch 全 0，仍不命名 dispatch flag、場景或內容類別。
- [x] M1.15：對 natural generic route 的 EWRAM dispatch object `0x02024750` 做一次性 write-watch；命中後以 static boundary 對上實際 `str r1,[r0]` at `0x08003a18`（watch stop `0x08003a1a`），source `r1/after-value=0x08691858`、destination `r0=0x02024750`。同一路徑仍重現 dispatch table index 86→`0x08011779`，但 `0x08691858` 的更上游 initializer 與 flag 語義維持 unknown。
- [x] M1.16：沿 `0x08003a0e → 0x08003c54` 反組譯 allocator-like helper；static 唯一 direct BL、function span `0x08003c54–0x08003c7e`、literal pool `0x08003c74 = 0x020258c8` 與 cursor `+4` flow 已固定。fresh mGBA route 取得 56 組 entry/return，所有組別都由 `LR=0x08003a13` 回推 `0x08003a0e`，且 `global_after = global_before + 4`、return `r0 = [cursor_before]` 全數相等；這只證明 opaque EWRAM cursor/value producer，不命名 allocator、object、場景或文本語義。
- [x] M1.17：反組譯 `0x08098c00` consumer，固定 `ldrb 0x08098c24` 後的 signed／`<=1`／`==4` branch topology 與 `0x08003e60` callsite；既有成功的 natural receipt 觀察到 buffer offset 8 的 opaque `0x01` → `0x08098c78`，但未提升為換行／等待／結束。新增 compare-instruction tracer 的重跑受 mGBA stale packet／point request transport 阻塞，精確記為 negative，不以 target hit 過度配對 source byte。
- [x] M1.18：把同一 consumer compare map 接到穩定的 `trace_m112_dispatch.py`／core GDB client；short／long natural routes 分別取得 loader return `1/3`，但 compare instruction 與 consumer breakpoint 都是 `0`。這是 route/instrumentation negative，與既有 EWRAM read-watch 觸發的 `0x01`→`0x08098c78` receipt 分開保存，不提升 `0x01` 語義。
- [x] M1.19：新增 `trace_m19_glyph_sink.py`，重用 core GDB client，以 scoped KEYINPUT、bounded detail-breakpoint 收斂與單步 writer receipt 介面固定 `0x080992dc` map lookup、`0x08098c62` glyph-field write、真正的 `0x08099462 BL 0x080995b0`、`0x08099580` kernel、`0x080995a6 str r1,[r2]` 邊界。fresh `start,a` 取得 loader `1`、8 筆 map／glyph-field receipt；長 natural route 取得 loader `3`，但本次自然場景的 `0x08098f68`／composer／kernel／writer 為 0。這是 bounded scene/instrumentation negative；既有 M1 baseline 的 VRAM write receipt 分開保存，不提升 Unicode、font pool 或 `0x01` 語義。
- [x] M1.20：新增 `analyze_m120_font_pool.py` 的 hash-only census；ROM map `0x08691644` bounded 為 121 entries，terminator `0x08691736`，wrapper literal `0x086916e5` 的 indexed-byte window 與 map index 對齊。既有 21 composer／63 renderer receipts 顯示 `0x020020c0` EWRAM source candidate 與 `0x06014000` VRAM candidate 的常見 base transition `0x40`，但另有 region-switch outlier，舊 receipt 也沒有 source/writer hash；stride／font pool／Unicode 維持 provisional/unknown。
- [x] M1.21：新增 `analyze_m121_font_source.py`，以 ARM7TDMI Thumb PC-relative literal 與 direct BL scan 證明 `0x08099424`／`0x0809947c` 兩個 composer 變體使用 `0x02000000 + computed offset` 與 `0x06010000 + computed offset`，另讀取 `0x02002800` config 與 `0x3ff` mask；`0x020020c0`／`0x06014000` 是計算結果候選，不是 ROM 單一 literal。對既有 ignored runtime receipt 重算 63 renderer entries、13 個 source address、21 個 destination address，兩個候選均出現，但 source hash／writer receipt 仍為 0，same-run pairing 維持 false；fresh writer capture 的 mGBA transport refresh 未取得，不把它寫成遊戲 negative。
- [x] M1.22：新增 `analyze_m122_codepage.py`，以 121/121 ROM map pair 的 strict Shift-JIS 解碼、ignored index 3087 corpus 與 fresh natural `start,a` map/glyph receipt 做 bounded correspondence。8/8 lookup 與 8/8 glyph-field 都符合 map pair→glyph index，前 4 個 runtime code-unit hash 與 corpus prefix 相符；後續 4 筆是同一畫面重複消費，不冒充完整字串。Shift-JIS 與 Unicode 身分、scene/category、翻譯 readiness 仍 candidate/unknown。
- [x] M1.23：新增 `extract_m123_bounded_corpus.py`，以已證實 custom tree worker／inverse encoder 產生 index `3064..3095` 的 32 筆 hash-only cohort；32/32 decode→encode 與相鄰 source-span 相等，32/32 可 strict Shift-JIS candidate decode，完整 marker offsets／opaque counts 保留但 `0x01` 不命名。ignored natural `start,a` receipt 對 index 3087 的 caller `0x08098b10` 與 buffer hash 相等，display receipt 只保存 hash；scene/content category 仍 unknown。
- [x] M1.24：新增 `analyze_m124_scene_witness.py`，對兩份 natural KEYINPUT receipt 做 static/runtime hash join：短 `start,a` 只有 selector `0x08098b10`／index 3087，長 route 另有 generic `0x08009252`／index 2678、2679；兩者共用 `[0,3342)` table，shared index 3087，display I/O hash 不同。4 筆 loader receipt 中 3 筆 static/runtime buffer hash 相等，index 2679 保留為 full-buffer hash mismatch negative；scene/category 與 `0x01` 語義仍 unknown。
- [x] M1.25：新增 `analyze_m125_control_corpus.py`，在 `index 3064..3095` 建立 32 筆 hash-only marker corpus；32/32 原始 leaf sequence decode→encode byte-identical，`0x00` 共 32 筆、`0x01` 出現在 21 筆／264 次，`0x04`／`0xff` 未出現在此 bounded cohort。把 `0x08098c24` read、`<=0x01 → 0x08098c78`、`==0x04 → 0x08098c80` 與 `0x08003e60` call topology 固化為 static gate；兩份 natural receipt 都實讀 `0x01` offset 8 並有 `0x08098c78` hit，但 branch source pairing 為 0、沒有 `0x00` 對照，因此 `0x01` 維持 opaque。encode guard 僅涵蓋原始 leaf 序列，不啟用任意翻譯文字 encode、marker 改寫或 ROM 回插。
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

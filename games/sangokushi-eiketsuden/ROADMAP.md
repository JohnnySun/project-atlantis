# 路線圖

## 里程碑 0：工作區與公開術語基線

- [x] 建立獨立 slug `games/sangokushi-eiketsuden/`，只涵蓋《三國志英傑伝》；不建立《孔明傳》資料。
- [x] 記錄公開產品代碼候選 `B3EJ`，並和 GBA ROM header game code 分欄；後者仍待日版 dump 驗證。
- [x] 閱讀 Project Atlantis 的 ledger 規範，建立 `research/`、`work/`、`translations/` 的原文隔離邊界。
- [x] 以中文 Wikipedia、巴哈姆特、光榮官方攻略書頁和日文 GBA 攻略 Wiki 交叉建立 `zh-TW` 術語候選。
- [x] 核對委派提供的日版 B3EJ ZIP；一個 4 MiB entry 已解到 ignored `roms/base/`，ROM、sav 和暫存輸出不進 Git。

## 里程碑 1：ROM 身分與唯讀資料偵察

- [x] 解析 header title、game code、maker code、revision、大小與補數校驗；記錄儲存值 `0xe1` 與計算值 `0x13` 的異常，不修改 ROM。
- [x] 記錄 CRC32、MD5、SHA-1、SHA-256；確認本地 dump 的 `B3EJ` header 與公開產品候選相符。
- [x] 掃描標準 Shift-JIS、候選指標表、GBA 位址指標、BIOS 壓縮標記與 bounded 候選計數。
- [x] 建立 `inspect_rom.py`、`scan_text_pointers.py` 與 ROM-independent tests；候選輸出只含偏移／計數，不含完整原文。
- [x] 完成一次有界 mGBA/GDB runtime capture：以共用 `core/gba` 工具確認 ROM 可執行、標題畫面 Mode 0／BG0–BG3 配置，並重建 title-screen tilemap；靜態文字池與 runtime 文字呼叫仍未對應。

## 里程碑 2：文本、字型與可逆路徑

2026-08-16 的 M2 bounded slice 已選定 table B entry 0（file target `0x078528`）並
建立 `tools/trace_m2_runtime.py`。M2.1 已以 static consumer chain 固定 table B 邊界與
44 entries，並由 Thumb code-flow 證實 table index／record load → wrapper／byte formatter。
M2.2 再把 formatter 靜態接到 output writer、SJIS codepage、glyph cache、VRAM copy 和
tilemap writer；runtime reachability、實際 index `<44` 與 runtime glyph identity 仍 pending。

- [x] 靜態定位劇情／系統／戰役相關候選 Shift-JIS 區段、四組 bounded pointer-table 候選與獨立 story-event E table；分類和範圍見 recon ledger。
- [x] 初步確認 `0x00` 終止、`0x0A` 換行、格式參數和候選控制序列；尚未確認完整字串結構。
- [x] M2.1 固定 table B 邊界（44 entries、26 unique targets），驗證 table B record 的 Shift-JIS／NUL 結構，並記錄未知控制 bytes 為 opaque。
- [x] M2.1 找到有效 Thumb static chain：`0x080262F8` literal → `0x080262FA–0x08026306` index／record load → `0x0800D8F0` wrapper → `0x0800D3FC` byte formatter／reader；glyph writer 尚未證實。
- [x] M2.1 建立 bounded analyzer、ignored decoded JSONL extractor、反組譯／邊界／結構測試；兩次乾淨 runtime retry 未取得 consumer hit，runtime edge 保留 pending。
- [x] M2.2 以有效 Thumb span、literal pool 和 callsite 驗證 `0x0800D3FC` stack output buffer → `0x0800CAD8` writer → `0x08008D18` SJIS renderer → `0x080650A4` codepage lookup → `0x080650DC` glyph expand → `0x080656D4` VRAM copy／`0x08008914` tilemap writer。
- [x] M2.2 建立 source-safe static analyzer、44-record decode→encode no-op verifier、三個 strict SJIS sentinel 的 codepage index／static glyph hash 交叉證據；不把 raw source、dump 或圖片寫入 Git。
- [x] M2.2 擴充 pipeline breakpoint harness，natural／controlled 事件分欄並記錄 r6 base、欄位、caller LR 與 actual index；M2.3 沿用並加入 builder、cache、VRAM、tilemap receipts。
- [x] M2.3 由 `0x080264A4` → `0x0801929C` static chain 證實 `r6+0x02` 是 builder count、`r6+0x1C` 是 event buffer；empty path 為 44，normal path的 runtime table bound 保持未證明。
- [x] M2.3 以明確標記的 controlled consumer fixture 觀察一筆 actual index `0 < 44`，並取得 B[0] → formatter → writer → glyph cache → 128-byte VRAM copy → tilemap 的 runtime receipts；自然 reachability 不冒充 confirmed。
- [x] M2.3 補上 listener／process／port readiness check、原生 mGBA direct 對照與 transport negative 記錄；只保存 metadata／hash，不提交 runtime artifacts。
- [x] M2.4 以兩條 fresh-process、single-connection 的 bounded natural path 取得可重現負證據，並由 `tools/m2_4_static.py` 固定 initializer → state gate `r4+0x14` → event poll → descriptor function-pointer → `0x08026054` 的正常 caller chain；自然 cohort 仍明確為 0，controlled fixture 不併入。
- [x] M2.5 以共用 `core/gba` 完成 startup→stable-title I/O 時序（第 9 秒穩定 `DISPCNT=0x1E40`），並用 `0x0805CF62` breakpoint 交叉證明 bounded KEYINPUT `r0` 注入有效；stable-title START／A 各一條 32-event natural path 仍為 builder／consumer／pipeline 0-hit，故只固化 runtime negative，不宣稱自然 `<44` 或自然 glyph receipt。詳見 `research/m2-5-stable-title-runtime-20260816.md`。
- [x] M2.6 以 register-specific KEYINPUT harness 完成 clean／event-system batch 2 patched
  ROM 各一條 title→menu bounded runtime path：`DISPCNT 0x1E40→0x1F40`、BG register
  維持、OAM renderer 24 visible sprites／三列 menu layout；兩次 B/E consumer 與
  formatter→glyph pipeline 均 0，patched／clean OAM／VRAM／render hash identical，
  所以只關閉 known-screen state-change cross，不冒充自然 consumer 或翻譯 menu QA。
  詳見 `research/m2-6-natural-menu-runtime-20260816.md`。
- [x] M2.7 完成第二條明確 menu-selection bounded negative（START→等待→DOWN×4→A×2）：
  32/32 stops 仍在 `0x0805CF5E` title poll，未命中 `0x0800C61C`、state gate、builder、
  B/D/E consumer 或 glyph pipeline；下一步轉 static 追 `0x0805D10C` menu owner，不再
  重複 title-only runtime path。詳見 `research/m2-7-menu-selection-negative-20260816.md`。
- [ ] 收集自然 consumer cohort 並證明自然 event index `<44`；controlled `0 < 44` 只關閉受控 fixture 的局部 gate，不是全域證明。
- [x] 分別確認四組 bounded candidate pool 的完整 NUL／Shift-JIS／LF／控制碼統計；A 183/183、B 44/44、C 4/4、D 28/28 可解，A 有 177 筆 LF，未把 noisy compression signature 當成文本壓縮。各池完整畫面語意與其餘 runtime glyph identity 仍分開 pending；M2.3 的 addressing 結論只限已驗證的 static／controlled path。
- [x] 建立 story-event E 的 bounded static boundary／consumer chain：`0x0CDB64/33`、33 unique targets、32/33 LF、33/33 strict Shift-JIS、0 opaque controls，並驗證 `0x080CDB64 → 0x08011904 → 0x080118C8 → 0x0800CAD8`；另以日文 GBA 攻略的夷陵／劉備生死結局流程建立 `provisional-known-screen-cross`，但 E 的 natural runtime、glyph receipt 和完整語意仍 pending，且不併入四池 custom-glyph source non-use。
- [x] 建立已知流程／標題渲染／static codepage 的 bounded cross-check：E:000–E:032 的
  hash-only 結局分組與公開夷陵／生死流程相符，common writer 的 codepage lookup／glyph
  addressing 與 controlled B[0] U+90E8 receipt 相接；runtime glyph pool 定位、E natural
  formatter→cache→VRAM receipt 與其餘 Unicode 身分仍分欄標為 pending／provisional，未以
  address 推導 Unicode。詳見 `research/m3-story-known-screen-cross-20260816.md`。
- [x] 寫出 `tools/extract_text_pools.py` 唯讀 decoder，輸出 ignored `research/sangokushi-eiketsuden-decoded.jsonl` 本機原文表與不含原文的 pool metadata；renderer 仍只使用共用 `core/gba` 工具。
- [x] 以 B0–B5 的 fixed-slot bounded patch 做一次選定 record 的 extract→encode→patch→re-extract
  round-trip；全池／全 ROM 的回插路徑仍保留到里程碑 4 驗收。

M2.3 的 evidence ledger 與 hash-only runtime receipt 見
[`research/m2-3-runtime-gate-20260816.md`](research/m2-3-runtime-gate-20260816.md)。

## 里程碑 3：有限量翻譯與 ledger

- [x] 從結構完整、固定槽位可容納且已通過 codepage coverage 的短批次開始；目前為
  Table B B0–B5 六筆、batch 2 的 19 筆、custom batch 3 的 B20 battle-effect label，
  以及 event-system D pool batch 1／2 的 15 個 non-empty unique menu／event labels。
  pool A system-item/class batch 1–5 再加入 34 個 item／class／battle-effect description records。自然
  畫面可達性仍是 runtime QA 缺口，不在此批次冒充完成。
- [x] 以 `restore_translations.rb` 產生本機 `work/*.jsonl`，保留來源 hash、上下文、譯文狀態和術語引用；
  兩批 restore input 與 work artifact 均 ignored。
- [x] 以 `strip_translations.rb` 產生不含 `source` 的提交帳本；二十八批共 108 筆已通過 schema、
  byte-identical restore→strip 比對和 repository safety。
- [x] 建立 event-system pool D 的 bounded source-free ledger、strict font coverage、
  fixed-slot patch／re-extract verifier 和 78-byte BPS；9/9 selected records 相符，
  28-entry pointer table 不變。完整事件池與自然 menu QA 仍待完成。
- [x] 建立明確授權 Unifont-T 的 custom glyph mapping、兩 plane encoder／verifier；
  D batch 2 的 6 unique／12 alias entries 與 Table B B20 的 1 entry 均完成 custom
  glyph plane match、fixed-slot re-extract 和 BPS round-trip。mapping 的 full-ROM raw
  code-unit non-use 與自然 runtime 仍待證明。
- [x] 以同一 custom-aware encoder 開始 pool A `system-item-class` batch 1；4 unique
  descriptions／5 selected entries 通過 custom glyph plane match、fixed-slot re-extract
  和 BPS round-trip。其餘 pool A records 仍待按語意／版面分批處理。
- [x] 完成 pool A `system-item-class` batch 2 的 6 個 class-conversion descriptions；
  5 custom glyph planes、6/6 selected entries re-extract／fixed-slot 和 BPS round-trip
  通過。其餘 pool A records 仍待處理。
- [x] 完成 pool A `system-item-class` batch 3 的 12 個 level-gated／class descriptions；
  8 custom glyph planes、12/12 selected entries re-extract／fixed-slot 和 BPS round-trip
  通過。`投石車` 等 wording 仍待臺灣術語與畫面審核。
- [x] 完成 pool A `system-item-class` batch 4 的 6 個耐久恢復 descriptions；existing
  codepage coverage `6/6`、selected alias 展開後 `31/31` re-extract／fixed-slot 和 BPS
  round-trip 通過，沒有新增 custom glyph。恢復量 wording 與自然 item screen 仍待審核。
- [x] 完成 pool A `system-item-class` batch 5 的 6 個通用戰鬥狀態效果 descriptions；
  existing codepage coverage `6/6`、selected re-extract／fixed-slot `6/6` 和 BPS round-trip
  通過，沒有新增 custom glyph；帶策略專名的戰鬥描述與自然戰役畫面仍待處理。
- [x] 完成 story-event E 的完整 33 筆 record-level 劇情批次 `E:000`、`E:001`、`E:002`、`E:003`、`E:004`、`E:005`、`E:006`、`E:007`、`E:008`、`E:009`、`E:010`、`E:011`、`E:012`、`E:013`、`E:014`、`E:015`、`E:016`、`E:017`、`E:018`、`E:019`、`E:020`、`E:021`、`E:022`、`E:023`、`E:024`、`E:025`、`E:026`、`E:027`、`E:028`、`E:029`、`E:030`、`E:031`、`E:032`；
  前三筆為 existing-codepage，後續批次使用 E-specific 292-record source-use gate，均為
  source-safe ledger、control/LF invariant、fixed-slot re-extract 和 BPS apply round-trip。
  batch 1／2／7／16／18 的 existing-codepage records、batch 3–6／8–15／17 各兩筆 E-specific custom record 也已通過相同 gate；公開流程交叉證據已記錄，仍須取得自然 E writer／畫面證據
  與人工終審，不以 pool A 固定池覆蓋率代替全遊戲進度。

## 里程碑 4：構建、BPS 與執行期 QA

- [x] 建立受限於 Table B fixed-slot 的遊戲專用 encoder、codepage／字庫 coverage 和嚴格的
  Shift-JIS／payload 長度／控制碼檢查；全遊戲字庫子集與版面規則仍待完成。
- [x] 從 clean ROM 建立兩個 existing-codepage Table B、兩個 existing-codepage pool-A、
  一個 existing-codepage event-system D，以及 custom Table B、custom event-system D、
  custom pool-A 三個 bounded BPS，以及 story-event E 五個 existing-codepage 加十三個
  E-specific custom bounded BPS；二十八個 BPS 全部套用後 byte-for-byte equality，並由
  bounded verifier 重新抽取 6/6、19/19、9/9、1/1、12/12、5/5、6/6、12/12、31/31、
  6/6、story E existing 2/2、1/1、2/2、2/2、2/2、custom 2/2、1/1、1/1、2/2、2/2、2/2、2/2、2/2、2/2、2/2、2/2、2/2 相符；全池／全 ROM
  round-trip 仍待完成。
- [ ] 在 mGBA 驗證已翻譯的核心場景、戰役事件和選單；未測畫面必須明確列出。
- [ ] 在所有必要 QA 通過前，維持 `status: research`，不發布 ROM，只發布可合法使用者套用的 patch。

## 接受條件

- ROM 身分：header／產品候選／版本／大小／四種雜湊都有明確證據，沒有把 B3EJ 型號直接當 header code。
- 文本解碼：同一字串可由 decoder 穩定抽出，原文表可通過 ledger restore，且抽出結果能以已知畫面或獨立資料交叉核對。
- 回插路徑：未翻譯資料回插後重新抽取與原文表一致，指標／壓縮／控制碼／字型覆蓋檢查全部通過。
- 翻譯批次：只提交 ledger，不提交原文；每批次有 string ID、術語版本、QA 結果與剩餘風險。

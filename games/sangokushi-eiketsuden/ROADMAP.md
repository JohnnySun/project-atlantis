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

- [x] 靜態定位劇情／系統／戰役相關候選 Shift-JIS 區段與四組 pointer-table 候選；分類和範圍見 recon ledger。
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
- [ ] 收集自然 consumer cohort 並證明自然 event index `<44`；controlled `0 < 44` 只關閉受控 fixture 的局部 gate，不是全域證明。
- [x] 分別確認四組 bounded candidate pool 的完整 NUL／Shift-JIS／LF／控制碼統計；A 183/183、B 44/44、C 4/4、D 28/28 可解，A 有 177 筆 LF，未把 noisy compression signature 當成文本壓縮。各池完整畫面語意與其餘 runtime glyph identity 仍分開 pending；M2.3 的 addressing 結論只限已驗證的 static／controlled path。
- [ ] 以已知畫面或執行期渲染交叉驗證 codepage；分開記錄 runtime glyph pool 定位和 Unicode 身分確認。
- [x] 寫出 `tools/extract_text_pools.py` 唯讀 decoder，輸出 ignored `research/sangokushi-eiketsuden-decoded.jsonl` 本機原文表與不含原文的 pool metadata；renderer 仍只使用共用 `core/gba` 工具。
- [x] 以 B0–B5 的 fixed-slot bounded patch 做一次選定 record 的 extract→encode→patch→re-extract
  round-trip；全池／全 ROM 的回插路徑仍保留到里程碑 4 驗收。

M2.3 的 evidence ledger 與 hash-only runtime receipt 見
[`research/m2-3-runtime-gate-20260816.md`](research/m2-3-runtime-gate-20260816.md)。

## 里程碑 3：有限量翻譯與 ledger

- [x] 從一個結構完整、固定槽位可容納且已通過 codepage coverage 的短批次開始；目前為
  Table B B0–B5 六筆 battle-effect label。自然畫面可達性仍是 runtime QA 缺口，不在此批次冒充完成。
- [x] 以 `restore_translations.rb` 產生本機 `work/*.jsonl`，保留來源 hash、上下文、譯文狀態和術語引用；
  restore input 與 work artifact 均 ignored。
- [x] 以 `strip_translations.rb` 產生不含 `source` 的提交帳本；B0–B5 已通過 schema、byte-identical
  restore→strip 比對和 repository safety。
- [ ] 先完成劇情／戰役事件小批次，再擴充武將、地名、官職、策略和道具；每批次記錄 string ID 集合。

## 里程碑 4：構建、BPS 與執行期 QA

- [x] 建立受限於 Table B fixed-slot 的遊戲專用 encoder、codepage／字庫 coverage 和嚴格的
  Shift-JIS／payload 長度／控制碼檢查；全遊戲字庫子集與版面規則仍待完成。
- [x] 從 clean ROM 建立 B0–B5 的 BPS，套用 BPS 後做 byte-for-byte equality，並由 bounded
  verifier 重新抽取 6/6 相符；全池／全 ROM round-trip 仍待完成。
- [ ] 在 mGBA 驗證已翻譯的核心場景、戰役事件和選單；未測畫面必須明確列出。
- [ ] 在所有必要 QA 通過前，維持 `status: research`，不發布 ROM，只發布可合法使用者套用的 patch。

## 接受條件

- ROM 身分：header／產品候選／版本／大小／四種雜湊都有明確證據，沒有把 B3EJ 型號直接當 header code。
- 文本解碼：同一字串可由 decoder 穩定抽出，原文表可通過 ledger restore，且抽出結果能以已知畫面或獨立資料交叉核對。
- 回插路徑：未翻譯資料回插後重新抽取與原文表一致，指標／壓縮／控制碼／字型覆蓋檢查全部通過。
- 翻譯批次：只提交 ledger，不提交原文；每批次有 string ID、術語版本、QA 結果與剩餘風險。

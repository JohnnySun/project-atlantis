# B3CJ 翻譯與逆向路線圖

狀態標記以可重現證據為準；`[~]` 表示部分完成，`[ ]` 表示尚未完成。

## M0：工作區與來源邊界

- [x] 只建立 `games/summon-night-craft-sword-3/` 內的 `game.yml`、README、ROADMAP、研究帳本與唯讀工具。
- [x] 登錄 B3CJ、容量、CRC、header checksum、公開 SHA-1，並保留外部候選與本機 readback 的區分。
- [x] 定義 `research` 原文表、`work` 工作檔與 `translations` 可提交 ledger 的分工。
- [x] 取得使用者提供的日版 ZIP，唯讀抽出單一 ROM 到 ignored `roms/base/`；未把 ROM 或 ZIP 納入 Git。

## M1：ROM 身分與唯讀偵察

- [x] 用 `tools/inspect_rom.py --strict` 確認 header title、game code、maker code、revision byte 與 header checksum。
- [x] 記錄本機 size、CRC32、MD5、SHA-1、SHA-256；與外部候選值分開保存。
- [x] 用 `tools/scan_static.py` 對 halfword-aligned Shift-JIS-shaped run、指標 run 與有界 LZ77／RLE decoder candidate 做掃描。
- [~] 壓縮／指標候選仍只有靜態證據；mGBA scripting/headless 路徑受 CLI 能力限制，未把候選升格為文本或資料表結論。

本里程碑的靜態報告只保留 offset、長度、計數、引用與 hash。共用 `core/gba` client／capture／renderer 的 6 項測試已通過；M2.3 另做過一次高位 `24387` 空閒檢查與本作自有 mGBA process 嘗試，但 mGBA 0.10.5 CLI 仍落在該 process 的 `2345`，core capture 在 `qSupported` timeout。程序已停止，runtime 不升格，且不把 runtime 實驗工具納入本作工具集。

## M1.5：csm3 導向的靜態文本工程

- [x] 固定 Data Crystal 遊戲頁／TBL oldid 與 csm3 commit、review 路徑及授權狀態；不提交第三方 source。
- [x] 依 csm3 `sub_08001D3C`、`sub_08012D30`、`sub_08012E14` 定位 type-2 resource table、LZ77 callsite 與 `PSI3` stream consumer。
- [x] 以本機 ROM 交叉驗證 type-2 table `0x1718ffc`、16-byte pointer units、LZ77 MSB-first flags、`PSI3`／`+0x10` stream 與 `0x0308 ... 0x0000` record。
- [x] 建立 bounded `tools/extract_static.py` 與測試；可由固定 B3CJ ROM 重抽 361 筆真實 record，完整日文 source 只寫 ignored JSONL。
- [x] 保留 stable `string_id`、pointer／payload provenance、compressed/decompressed hash 與 control token；tracked 文件不含完整原文。
- [~] 完成完整 VM opcode／換行語意、修改長度契約與回插路徑；font lookup／glyph identity 已在 M2.2 static 範圍完成，但 palette／runtime／正式 encoder 仍未完成。

M1.5 不依賴 mGBA GDB listener；`RUNTIME-003` 仍是 live RAM／VRAM 交叉驗證的獨立 blocked 項，不是本里程碑的 gate。格式證據與重跑命令見 [`research/static-format.md`](research/static-format.md)。

## M2.1：控制碼保真與解壓 stream round-trip

- [x] 依固定 csm3 VM dispatch／handler callsite 結構化 `0x0308` text record、`0x0309` input/state、`0x030A` two-expression state handler，以及周邊 `0x0001/2/3/6` 的已證實參數形狀。
- [x] expression parser 保留 `0x0000` terminator、已證實 operand width 與未知 expression word；未能由 callsite 命名的 `0x0302/4/16/0x047e` 以 opaque token 保存。
- [x] stable `string_id`／pointer provenance 不變；ignored source table 新增 `control_structure`、`following_controls`、`record_sha256` 與 length-contract metadata。
- [x] 對 13 個含 record 的 resource、361 筆 record 做 source Shift-JIS re-encode 與 decoded PSI3 stream no-op round-trip：`32092` bytes，original/encoded aggregate SHA-256 相同。
- [x] 明確分類相同 byte length 可在 record/stream 層原地處理、zero padding 縮短 blocked、變長需 resource rebuild；未宣稱完整 ROM 回插。
- [ ] 建立可修改翻譯的 codepage/font encoder、未知 VM handler、pointer relocation、LZ77/container rebuild 與 ROM-level verifier。

M2.1 的完整 opcode／round-trip／length-contract 收據見 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)。

## M2.2：字型／glyph 鏈與 static POC

- [x] 從固定 csm3 commit 的 `sub_0800D084`、`sub_08001F14`、`sub_0800348C`、`sub_08003620`、`sub_080036F8`／`sub_0800379C` 與 `sub_0800B730` callsite 往下追 renderer、font loader、lookup 與 writer；以本機 B3CJ function hash／literal 交叉驗證，不只採外部 symbol 名稱。
- [x] 定位 type-3 resource `id=2` 的 `BIT` font：payload `0x14d5c6c`、glyph base `0x14d5c88`、12×12 active bits、row stride 2、cell stride `0x18`、header metric `0c 00 0c 00` 與 2144 physical slots。
- [x] 建立 raw memory-order Shift-JIS code unit → table A/B → `glyph_id` → cell file offset 公式；以 `正`、`直`、`同`、`部`、`屋`、`ら`、`す`、`γ` 八個樣本分開記錄 Unicode identity 與 addressing evidence。
- [x] 掃描實際 strict code format：6879 accepted pairs、2087 mapped slots、27 個未引用全零可用槽 `0x845..0x85f`；30 個非空不可尋址槽 `0x141..0x15e` 與 3 個 out-of-resource table target 不分配。
- [x] 建立 `tools/inspect_font.py`、靜態 12×12 renderer、Unifont 17.0.05 來源／授權紀錄與測試；static POC 只把 opaque `ec48`／`ec49` 暫映射到 `0x845`／`0x846`，並 render adjacent untouched `0x844`。
- [x] POC 的 table/cell 修改區域共 52 bytes，固定 source 下實際非零 byte diff 為 43；ROM／PGM／summary 留在 ignored `work/`，未更新 header／script container，未宣稱翻譯、可發布 patch 或 runtime QA。
- [ ] 證實 palette、writer 的實際 VRAM/OAM layout、fallback 語意、out-of-resource targets、font/resource encoder 與 ROM-level insertion；RUNTIME-003 仍為獨立 live evidence blocker。

M2.2 的完整字型、slot、source/license 與 POC 收據見 [`research/m2.2-font.md`](research/m2.2-font.md) 與 [`research/font-sources.md`](research/font-sources.md)。

## M2.3：fail-closed glyph allocation 與 bounded record POC

- [x] 固定 `research/m2.3-glyph-manifest.json`：只允許 `0x845..0x85f`，保留既有 mapping，拒絕範圍外、重複 code unit／slot、strict Shift-JIS collision、source／ROM／font hash mismatch 與容量超限。
- [x] 以 `ec48`／`ec49` 兩個 opaque static POC glyph 及兩筆 4／2-byte 短 record 實作 deterministic encoder；不把 static POC code unit 當成日文翻譯或最終 codepage 決策。
- [x] 驗證 font mapping／cell、record、PSI3 stream byte-identical；兩個 LZ77 output 分別為 `485 <= 496` 與 `1652 <= 1664`，只在原 resource span 內重建，不宣稱完整 pointer／header／BPS 回插。
- [x] 測試 fail-closed rejection：slot／code-unit duplicate、strict collision、hash mismatch、既有 fallback／out-of-resource 狀態與 resource capacity overrun。
- [~] 執行一次獨立 runtime QA：`24387` preflight 空閒，但 `-C ports.qt.gdbPort=24387` 未改變 CLI stub；自有 PID `26484` 的 `2345` 對 core `qSupported` timeout。palette、writer destination、VRAM/OAM layout 與畫面可讀性維持 blocked。

M2.3 完整 static／runtime 收據見 [`research/m2.3-poc.md`](research/m2.3-poc.md)。下一個最小缺口是可重現的 renderer runtime evidence（或等價 static writer／VRAM destination 證據），再評估第一筆經術語審核的同長度 zh-TW 翻譯；本切片不開始批量翻譯。

## M2.4：runtime handshake diagnostic 與 static writer→destination

- [x] 唯讀 review 其他成功 session 的 `-C gdb.port=<high-port> -C skipBios=1 -g` 啟動方式、單次 GDB client、ACK／delay／一次 timeout retry 邊界；不再使用 `ports.qt.gdbPort` shim。
- [x] 以本作 M2.3 POC ROM、獨立高位 port `24763`／`24764` 做兩輪 fresh process ownership／listener 檢查；第一輪 GUI PID `29811` 無 `24763` listener，第二輪 headless 明確輸出 `Debugger: Couldn't open socket`，兩個 process 均已停止。
- [x] 建立 `tools/runtime_m2_4.py` 與測試；對每輪已釋放 port 收到可重現的 `ConnectionRefusedError`，並保存 ignored diagnostic 的 client 設定與失敗邊界；沒有假造 `qSupported`、breakpoint 或 watchpoint hit。
- [x] 以本機 function hash／callsite 收斂 `sub_080036F8 → sub_08002CB4` 的 `0x80`、`sub_0800379C → sub_080031E8` 的 `0x40` RAM/output-buffer contract，並重驗 changed `0x845/0x846` 與 adjacent untouched `0x844` static glyph POC。
- [~] runtime gate 仍 blocked：尚無 live font cache、lookup／writer destination、VRAM／palette／tilemap／OAM 或畫面可讀性；controlled argument hijack 尚未執行，也未準備 translation ledger candidate。

M2.4 完整啟動、PID／listener、client 設定、static writer 邊界與下一缺口見 [`research/m2.4-runtime.md`](research/m2.4-runtime.md)。這個切片沒有開始大批翻譯，也沒有宣稱 POC 可發布。

## M2.5：首批 zh-TW ledger／static build

- [x] 從 ignored 361-record source table 選出 resource 24 的結構完整短內容群；四筆同時重建因 LZ77 超過原 span 而 fail closed，收斂為 `b3cj:t2:024:0x0064` 一筆 target，沒有把 `ec48`／`ec49` POC 假資料當翻譯。
- [x] 固定 `research/m2.5-batch-plan.json`：source／ROM／font／target hash、14-byte／7-cell／1-line contract、`0x0308`／`0x0000` 控制形狀、adjacent untouched IDs，以及 `ec64/ec65/ec66`→`0x847/0x848/0x849` 的 fail-closed glyph allocation。
- [x] 由 `build_m2_5_batch.py prepare` 建立 ignored source adapter，通過 `restore_translations.rb` → ignored `work` → `strip_translations.rb`，產生只含 `source_hash`、target、`ai_draft` status 與 review metadata 的 tracked ledger。
- [x] 以實際 target builder 重建 font mapping／cell 與 resource 24，重新抽取 361 筆 record：target `1`、untouched `360`，adjacent records 與其他 resources 保持 byte-identical；原 span `1379/1392`、新 span `1392/1392`。
- [x] 以 core BPS create／apply 做 byte-for-byte round-trip，target ROM SHA-256、BPS SHA-256、size 與 applied hash 留在 [`research/m2.5-batch.md`](research/m2.5-batch.md)；ROM／BPS／raw source／work 均 ignored。
- [~] runtime 仍 pending：沒有自然畫面 reachability、palette、VRAM／tilemap／OAM、live glyph readability 或人工翻譯 QA；本批只是 `ai_draft` static POC，不是發布 patch。

M2.5 只完成第一個有界 static translation slice。下一個最小缺口是先完成這一筆的人工／術語／字型審核，再在 runtime 解鎖後驗證畫面；不擴大到劇情、支線、夥伴、鍛造、戰鬥或道具的大批翻譯。

## M2.6：第一筆翻譯 runtime renderer QA

- [x] 以 M2.5 ignored target ROM／BPS 做前置 hash guard：clean base CRC32 `12afae5d`／SHA-256 `39bc…fad2d`、target SHA-256 `da9c…5b16`、BPS SHA-256 `4261…e5b`、applied ROM byte-identical。
- [x] 建立 `tools/runtime_m2_6.py` 與測試；先驗證 target ID `b3cj:t2:024:0x0064`、`ec64/ec65/ec66`→`0x847/0x848/0x849` static render、adjacent glyph `0x846` base／target cell hash，以及 361／1／360 re-extraction receipt，再只開一條 core GDB connection。
- [x] 完成兩輪 fresh launcher／process ownership 收據：高位 port `25126` 無 listener；GUI PID `50537` 啟動後退出，headless PID `50654` 輸出 `Debugger: Couldn't open socket`；兩個自有 process 均已停止，沒有附加其他 session。
- [~] qSupported／renderer runtime gate 仍 blocked：兩份 diagnostic 都是 `handshake=blocked`，本環境 socket connect 回報 `PermissionError [Errno 1]`；沒有 breakpoint／watchpoint、font cache、writer destination、palette、VRAM／tilemap／OAM 或畫面可讀性證據。這是 transport-only negative，不是 ROM／譯文失敗。
- [ ] 使用 `/private/tmp` compile-time GDB-port mGBA build，或在允許 localhost socket 的環境，以同一 hash-guarded diagnostic 重跑；runtime 解鎖前不擴大第二筆翻譯、不改 `ai_draft` 狀態。

M2.6 已把 static target／adjacent proof 與 runtime transport failure 分開記錄。完整 launcher、PID、port、hash、static glyph 與下一個 runtime 方案見 [`research/m2.6-runtime.md`](research/m2.6-runtime.md)；這一輪沒有宣稱畫面通過或可發布 patch。

## M2.7：M2.5 target transport-only QA

- [x] 只處理既有 target `b3cj:t2:024:0x0064`；M2.5 base／target／BPS／applied hash guard、361／1／360 re-extraction、`0x847/0x848/0x849` changed static proof 與 adjacent `0x846` proof 均重跑通過，沒有新增第二筆翻譯。
- [x] 以 `lsof` 先確認高位 port `25273`／`26371` 無 listener，再以兩個不同的既有 mGBA binary 進行 fresh process；兩個 launcher 都使用 `-C gdb.port=<high-port> -C skipBios=1 -g` 並指向本作 M2.5 target。
- [x] 兩個自有 foreground process 均明確回報 `Debugger: Couldn't open socket`，啟動前後指定 port 都無 listener，並已乾淨停止；沒有附加或終止其他 session。PTY wrapper 未暴露 child OS PID，故不虛構 PID。
- [x] 建立 `tools/runtime_m2_7.py`／測試；重用 M2.6 static guard、`core/gba/gdbstub_client.py` 的單次 connection、`0.08s` packet delay、ACK／一次 retry；兩份 ignored diagnostic 在 `connect()` 前得到 `PermissionError [Errno 1]`，`qSupported` 未送出。
- [~] runtime gate 仍 transport-only blocked：沒有 natural／controlled consumer hit、font cache、writer destination、palette、VRAM／tilemap／OAM 或 changed／adjacent live render；`ai_draft` 不變，不宣稱畫面通過或可發布。
- [ ] 在允許 localhost socket 的環境，或以 `/private/tmp` compile-time GDB-port mGBA build，重跑同一 hash-guarded probe；解鎖前不擴大翻譯。

M2.7 的 launcher、listener、single-connection error、safe alternatives 與重跑命令見 [`research/m2.7-runtime.md`](research/m2.7-runtime.md)。這個切片達到 transport evidence boundary 即停止，不把 `PermissionError` 解讀成 ROM／譯文失敗。

## M2.8：靜態 pointer／record／layout contract audit

- [x] 以固定 B3CJ ROM identity guard 重抽 13 個含文字 resource、361 筆 record，並確認 source Shift-JIS re-encode `361/361` 與 stable record-contract aggregate hash。
- [x] 交叉驗證 type-2 pointer unit 為 16 bytes；13 個 pointer entry 收斂為 11 個 payload groups，resource `9`／`10` 是 resource `11` 的 zero-span alias，positive span 不重疊且 compressed size 不超過 span。
- [x] 建立 `tools/audit_layout.py`／測試，輸出只含 offset、span、opcode 計數、length histogram、opaque count 與 hash 的 ignored summary；不輸出完整日文或 raw stream。
- [~] record-level 只確認 `0x0308` inline segment／`0x0000` terminator 與相同 byte length 契約；line/page/wait、glyph width、變長／padding、LZ77／PSI3 container rebuild 與 runtime layout 仍 unknown。

M2.8 的 pointer／record／layout 收據見 [`research/m2.8-layout.md`](research/m2.8-layout.md)。這個切片沒有擴大翻譯或宣稱完整 ROM 回插；opaque control 與 runtime transport boundary 仍分開保留。

## M2：文本與字型格式

- [~] 定位已確認的 `PSI3` script resource、bounded text record 與部分 VM control shape；仍需把劇情／支線／夥伴／鍛造／戰鬥／道具群組完整分類。
- [~] 已確認 type-2 pointer、GBA LZ77、script bytecode、record-level Shift-JIS 與部分 expression／control width；未知 VM opcode、完整換行／分頁語意仍待命名。
- [x] 定位字型資料與渲染器；分開驗證 glyph addressing 與 glyph identity（static M2.2 範圍）。
- [~] palette、writer output、VRAM/OAM layout 與 live screen 仍待 runtime 交叉驗證。
- [~] 確認 stable string ID、pointer alias／span、控制碼與相同 byte length 契約；line/page、字寬／行數上限及未修改內容的完整回插契約仍待證實。
- [ ] 以 ROM-to-VRAM byte match、已知畫面內容或全語料庫上下文重讀交叉確認解碼。

## M3：原文表與可逆試驗

- [x] 由遊戲專用 decoder 產生本機 ignored `research/summon-night-craft-sword-3-decoded.jsonl`，每行含 `string_id`、`locale`、`source_text`、structured controls、length contract 與 `provenance`；M2.5 已有 1 筆可提交 translation ledger，M3 validator 再以 source hash／stable ID／core restore-strip round-trip 重驗。
- [x] 先選一個可達候選、短且有明確結構的 UI 批次，不一次處理全遊戲；M2.5 目前只固定一筆 static candidate，runtime 可達性仍 pending。
- [x] 建立本機 `work/*.jsonl`，明寫 `zh-TW`、`ai_draft`、`context`、`terms` 與 byte/layout contract。
- [x] 用 `core/ledger/restore_translations.rb` 與 `strip_translations.rb` 驗證 source hash 與帳本往返。
- [x] 只提交不帶 `source` 的 `translations/*.jsonl`，並通過 `scripts/check-repository-safety.rb`；人工審核尚未完成。

M3 ledger workflow 的 source adapter、hash guard、restore／strip receipt 與負面測試見 [`research/m3-ledger.md`](research/m3-ledger.md) 及 `tools/validate_ledger.py`。

## M4.1：resource-22 bounded zh-TW static batch

- [x] 從 361 筆 local source table 選出 resource 22 的一筆 12-byte／6-code-unit、無 opaque control 短 label；source hash、provenance、`0x0308`／`0x0000` 與後續 control shape 固定。
- [x] 依 `restore → work → strip` 產生只含 hash 的 `translations/m4.1-wood-chopping.jsonl`；target 明寫 `zh-TW`、`ai_draft`，無專有名詞，未把 source text 寫入 tracked ledger。
- [x] 只配置 `0x84a`／`0x84b` 的 `ec67`／`ec6c`，保留既有 mapping，拒絕 out-of-resource `ec68`；existing `新`／`手`／全形空白 mapping 與 adjacent glyph `0x84c` 通過 static proof。
- [x] cumulative builder 先重建 M2.5，再加入 M4.1；全部 361 筆 re-extract 為 target `2`／untouched `359`，resource 22 compressed `485→493`／span `496`，BPS apply byte-identical。
- [~] target 仍是 `ai_draft`；人工／術語／字型 review、runtime screen readability 與發布資格仍 pending。

M4.1 的 source hash、glyph allocation、capacity、cumulative re-extraction 與 BPS 收據見 [`research/m4.1-wood-chopping.md`](research/m4.1-wood-chopping.md)。

## M4.2：resource-16 bounded zh-TW static batch

- [x] 從 361 筆 local source table 選出 resource 16 的一筆 10-byte／5-code-unit、無 opaque control 短警告標籤；source hash、provenance、`0x0308`／`0x0000` 與 following control shape 固定。
- [x] 先以 resource 22 下一個候選的實際壓縮結果 `500/496` 做 capacity fail-closed，再收斂到 resource 16 的 `180/192` 原 span；不放寬容量、不做 pointer relocation。
- [x] 依 `restore → work → strip` 產生只含 hash 的 `translations/m4.2-warning-label.jsonl`；target 為 `zh-TW`、`ai_draft`，沒有專有名詞或新增 glyph allocation。
- [x] cumulative builder 先重建 M2.5／M4.1，再加入 M4.2；全部 361 筆 re-extract 為 target `3`／untouched `358`，existing glyph mapping／adjacent records 保持 byte/render identical，BPS apply byte-identical。
- [~] target 仍是 `ai_draft`；三筆 target 的人工／術語／字型／版面 review、runtime screen readability 與發布資格仍 pending。

M4.2 的 source hash、capacity rejection、existing-mapped-glyph proof、cumulative re-extraction 與 BPS 收據見 [`research/m4.2-warning-label.md`](research/m4.2-warning-label.md)。

## M4.3：resource-25 bounded zh-TW static batch

- [x] 從 361 筆 local source table 選出 resource 25 的一筆 8-byte／4-code-unit、無 opaque control 短語氣標籤；source hash、provenance、`0x0308`／`0x0000` 與 following control shape 固定。
- [x] 配置唯一新增 `ec6d`→`0x84c`，保留既有 `8163`／`8140` mappings，拒絕 fallback、out-of-resource target、重複 slot／code unit 與容量超限；Unifont cell 與 adjacent `0x0ac` static proof 通過。
- [x] 依 `restore → work → strip` 產生只含 hash 的 `translations/m4.3-ellipsis-label.jsonl`；target 為 `zh-TW`、`ai_draft`，沒有專有名詞。
- [x] cumulative builder 先重建 M2.5／M4.1／M4.2，再加入 M4.3；全部 361 筆 re-extract 為 target `4`／untouched `357`，resource 25 compressed `1652→1655`／span `1664`，BPS apply byte-identical。
- [~] target 仍是 `ai_draft`；四筆 target 的人工／術語／字型／版面 review、runtime screen readability 與發布資格仍 pending。

M4.3 的 source hash、glyph allocation、cell／capacity、cumulative re-extraction 與 BPS 收據見 [`research/m4.3-ellipsis-label.md`](research/m4.3-ellipsis-label.md)。

## M4：有限量翻譯與術語

- [~] 已建立四筆 M4 cumulative static target；M5.2 另加入第五筆 resource-24 capacity-expansion slice；仍需依日文原文與上下文完成劇情、支線、夥伴、鍛造、戰鬥、道具的完整分批工作帳。
- [ ] 專有名詞以 Wikipedia zh-tw、巴哈姆特及其他獨立社群資料交叉核對；不把單一 patch 的譯名視為定論。
- [ ] 建立 `translations/glossary.zh-TW.tsv`（只收已核對術語，不放完整原文段落）。
- [x] 對目前四筆 M4 bounded batch 做字寬、行數、缺字、控制碼、簡繁漏入與 target metadata QA；M5.2 另由 relocation builder 做同等 fail-closed target contract；完整用語一致性與人工翻譯 review 仍待進行。

M4 target-side QA 的工具與固定範圍見 [`research/m4-batch-qa.md`](research/m4-batch-qa.md)。

## M5：回插、BPS 與 runtime QA

- [~] 建立本作專用 bounded encoder／font allocation／回插器；缺字、來源 hash、控制碼與長度不符時 fail closed。已完成單一 resource 的 pointer relocation static slice，完整多 resource／alias policy 尚未建立。
- [~] 從 bounded static 重建 ROM 重新抽取，確認未修改 record 與目標 target 吻合；M5.2 已涵蓋 resource-24 relocation，尚非完整 ROM container coverage。
- [~] 生成 BPS，套用後做 byte-for-byte round-trip，記錄 target CRC32、patch size、SHA-256；目前為五筆 cumulative `ai_draft` static POC。
- [ ] 以 mGBA 測試實際可達的劇情／支線／夥伴／鍛造／戰鬥／道具畫面，保留未測試範圍。
- [ ] 只有完成上述收據後，才評估 zh-TW 發布。

## M5.1：static type-2 pointer relocation POC

- [x] 對 clean B3CJ resource 24 找到明確 zero-filled、16-byte table-relative aligned 的 ROM 目的區 `0x1fbb1fc`；目的區沒有 aligned ROM pointer reference，且不與已知 table/resource spans 重疊。
- [x] 建立 `tools/relocate_resource_poc.py`／測試；只更新 resource 24 directory relative pointer/span，重導後 361 筆 stable records、decoded stream 與 record aggregate byte-identical。
- [~] 這只證實單一 resource 的 static directory redirect；多 resource／alias、變長資源重建、ROM-level BPS policy、runtime 與發布資格仍 pending。

M5.1 的目的區 guard、pointer receipt、重抽取 hash 與邊界見 [`research/m5.1-pointer-relocation.md`](research/m5.1-pointer-relocation.md)。

## M5.2：resource-24 capacity-expansion translation slice

- [x] 由 M5.1 的 zero-filled destination 建立 `b3cj:t2:024:0x0078` ledger；實際執行 `restore → work → strip`，tracked ledger 只有 source hash、target 與 review metadata，target 維持 `zh-TW`／`ai_draft`。
- [x] 以 fail-closed encoder 保留既有 `ec65→0x848`，只配置 `ec6e→0x84d`；target 12 bytes／6 code units，拒絕 source／font／ROM hash drift、fallback／非空 cell、重複 slot／code unit 與容量超限。
- [x] 將 resource 24 從 `0x17231fc`／`1392`-byte span 重導至 `0x1fbb1fc`／`1536`-byte span，pointer relative units `0xa20→0x8a220`；destination alignment、zero fill、pointer reference 與 overlap guards 通過。
- [x] 累積重建 M2.5／M4.1／M4.2／M4.3 後完成 M5.2；361 筆 re-extract 為 target `5`／untouched `356`，resource 24 compressed `1392→1396`，local adjacent records／glyph 保持 byte/render identical。
- [x] 產生 `4814`-byte BPS，套用後 ROM 與 target `da3b83b5470f278f455672021e2ae87452bc92d93fdbf1126c0e994dde757cb1` byte-identical；target CRC32 `c81e7eb5`，所有 ROM／BPS／summary 仍 ignored。
- [~] 這是 static-only slice；五筆 target 仍需人工／術語／字型／版面 review，runtime transport／consumer／VRAM／palette／畫面 QA 與發布資格仍 pending。

M5.2 的 plan、ledger 分界、pointer／font／re-extract／BPS receipts 見 [`research/m5.2-reward-relocation.md`](research/m5.2-reward-relocation.md)。

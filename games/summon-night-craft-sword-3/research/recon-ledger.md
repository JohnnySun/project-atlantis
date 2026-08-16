# B3CJ 唯讀偵察帳本

本帳本只保存可公開的研究判斷、證據索引與下一個可重現檢查，不保存 ROM、抽出的原文、完整字串表、渲染圖或 OCR 結果。原文若能從本機合法 ROM 解出，固定放在被 `.gitignore` 排除的 `research/summon-night-craft-sword-3-decoded.jsonl`；實際翻譯編輯放在被排除的 `work/`；只有經 `core/ledger/strip_translations.rb` 產生、沒有 `source` 欄位的 `translations/*.jsonl` 才能提交。

## 狀態定義

- `candidate`：來自公開資料或靜態掃描，尚未由本機 ROM 或執行期資料交叉確認。
- `confirmed`：至少兩種互相獨立的證據吻合，且可由遊戲專用腳本重跑。
- `rejected`：已在指定測試情境下被反例推翻；記錄測試情境，避免下次誤用成永久結論。
- `blocked`：需要本機 ROM、模擬器執行期狀態或其他外部輸入，現階段不能安全猜測。

## 目前紀錄（2026-08-16）

| ID | 項目 | 判定 | 證據／重跑方式 | 下一步 |
| --- | --- | --- | --- | --- |
| `ROM-ID-001` | 目標是日版 GBA、game code `B3CJ` | `confirmed` | 使用者提供的 ZIP 只有一個 33554432-byte entry；`inspect_rom.py --strict` 讀得 `CRAFTSWORD H`／`B3CJ`／maker `D9`／revision `0` | 保留此 clean dump 的完整 hash，後續工具只接受同一身分 |
| `ROM-ID-002` | 本機 ROM 的容量、CRC32、header checksum | `confirmed` | `size=33554432`、`CRC32=12afae5d`、stored／calculated header checksum 均為 `6b`；與 Data Crystal 候選一致 | 不把其他 dump、patch 或不同 revision 混入 |
| `ROM-ID-003` | 本機 ROM 與公開 csm3 build/reference SHA-1 是否一致 | `confirmed` | 本機 `SHA-1=3f5253fcf57e07ce52472bd29a61d16b98a12376`，與 [csm3](https://github.com/jiangzhengwenjz/csm3) 公開 reference 一致；只作身分交叉比對 | 只參考公開工程資訊，不把反編譯資產或完整腳本帶入本作 |
| `ROM-ID-004` | ZIP 來源與 ignored extraction 邊界 | `confirmed` | ZIP 唯讀 listing 為單一 32 MiB entry；實體檔為 ignored `roms/base/B3CJ-jp-from-zip.gba`，ROM／ZIP 未 stage | 後續重跑仍使用 ignored 路徑，不在 Git 保存來源檔 |
| `EXT-001` | Data Crystal 遊戲頁／TBL 的固定版本與使用界線 | `confirmed` | 固定 [遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650)、[TBL oldid=53006](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006)；[Community](https://datacrystal.tcrf.net/wiki/Data_Crystal/Community) 說明站內資料的 GFDL 基礎；shell raw fetch 403，未把 HTML 快取進 repo | 只保存 oldid、格式結論與 provenance，不匯入整份表格 |
| `EXT-002` | csm3 固定 revision、license review 與本機身分 | `confirmed` | 固定 commit `7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2`；`csm3.sha1` 與本機 ROM SHA-1 一致；固定 checkout 未找到 root LICENSE/COPYING/NOTICE，僅於 `/private/tmp/csm3-review-b3cj` 唯讀 review | 不提交第三方 source／資產；只保留 callsite 與 commit 索引 |
| `TEXT-001` | 主日文點陣字型可能使用 16-bit、類 Shift-JIS 的碼值（例如 `0x8140` 起的表） | `candidate` | Data Crystal TBL 線索；本機掃描在 `0x79d26a` 找到 little-endian 179 units／134 個可解碼 unit，在 `0x145364c`、`0x145374c` 找到 113-unit runs；候選均無 ROM pointer reference | 需以反組譯、ROM-to-VRAM byte match 或文字畫面證實，不能直接建 decoder |
| `STATIC-TEXT-001` | 常見日文 probe 是否為 uncompressed script | `candidate` | direct `はい` 15 次、`セーブ` 10 次、`ロード` 4 次等命中；probe bytes 可出現在 binary／UI 資產，沒有字串邊界或 control-code 證據 | 只把 offset 留作後續定位線索，不把 probe 命中當原文表 |
| `STATIC-PTR-001` | ROM pointer table／指標 run | `candidate` | `scan_static.py` 找到 150059 個 aligned ROM-address words、1750 個至少 4 words 的 runs；這也可能是 literal pool／jump table | 需要 THUMB control-flow 或 runtime load site 交叉確認 |
| `STATIC-COMP-001` | GBA LZ77／RLE decoder 可消費的資料候選 | `candidate` | 有界掃描每種最多 2048 個 header、宣告展開上限 `0x40000`；保留 32 個最大候選，例：LZ77 file offset `0xc9f0d8`、RLE `0xc6cabc` | decoder 可消費不代表 payload 是文本；需先找到 caller／用途，再決定是否解壓 |
| `STATIC-SCRIPT-001` | csm3 導向的 type-2 script resource table 與 16-byte pointer units | `confirmed` | `gUnk_09718FFC` 位於 file `0x1718ffc`、大小 `0x284`，解析 ID `0..78`；`src/main.c:480-505` 的 pointer resolver 與本機 table entries 共同重現 payload；`tools/extract_static.py` 對 resource 9、12、14、24 等成功落址 | 以固定 table 續分類劇情／支線／夥伴／鍛造／戰鬥／道具群組 |
| `STATIC-SCRIPT-002` | LZ77 → `PSI3` → `+0x10` halfword stream | `confirmed` | csm3 `src/script.c:51-63` 呼叫 `LZ77UnCompWram`，`src/script.c:78-88` 消費 buffer `+0x10`；本機 bounded decoder 讀到 `PSI3` 並以 MSB-first flags 解壓 13 個 resource IDs | 繼續命名其他 VM opcode，不把 dispatch table 當文字指標表 |
| `STATIC-SCRIPT-003` | type-2 pointer／payload span／alias contract | `confirmed`（static） | `tools/audit_layout.py` 以固定 ROM hash 重抽 13 個含 record resource；16-byte pointer unit 形成 11 個 payload groups，resource `9`／`10` 為 resource `11` 的 zero-span alias，所有 positive span 不重疊且 compressed size 不超過 span | 只證實 static table relationship；pointer relocation、compressed container rebuild 與 ROM-level insertion 未完成 |
| `STATIC-SCRIPT-004` | single-resource type-2 pointer relocation POC | `confirmed`（static bounded） | `tools/relocate_resource_poc.py` 將 resource 24 directory entry `0x17190c4` 從 payload `0x17231fc` 重導至 zero-filled `0x1fbb1fc`（relative units `0x8a220`、span `1392` bytes）；destination aligned pointer references `0`、不與已知 spans 重疊；361/361 stable records、decoded stream 與 record aggregate byte-identical | 只證實單一 resource redirect；多 resource／alias、變長 rebuild、ROM checksum／BPS policy 與 runtime 仍 unknown |
| `STATIC-CODEPAGE-001` | bounded `0x0308 ... 0x0000` record 的 codepage | `confirmed` | 13 個 resource IDs 共 361 筆；marker／terminator 以 little-endian halfword 識別，marker 後 raw bytes 以原始記憶體順序 strict Shift-JIS decode；多筆 raw length／SHA-256 可重現，並與固定 TBL 線索交叉核對 | M2.2 已另以 font lookup／cell／identity 證據接上；palette／VRAM 與完整排版仍不由 record-level decode 推定 |
| `CONTROL-001` | 已命名的 record 周邊 opcode／expression 形狀 | `confirmed`（bounded） | 固定 csm3 `sub_080127E4` dispatch 與 handler callsite 證實 `0x0308`、`0x0309`、`0x030A`、`0x0001/2/3/6` 的 parser shape；每筆最多向後解析 8 個 command，未知 `0x0302/4/16/0x047e` 留 opaque | 追查未知 handler；不把 `0x0309`／`0x030A` 猜成換行／分頁 |
| `CONTROL-002` | PSI3 stream／record no-op round-trip | `confirmed`（decoded stream layer） | 13 resources、361 records、32092 stream bytes；source Shift-JIS re-encode `361/361`；original／encoded aggregate SHA-256 均為 `6fda79e61316e3e941e72bad156206bb855a352c546f95d3c1dba2a474025706`；opaque tokens `203`、rejected marker `1` | 仍未重建 LZ77 compressed bytes、resource pointer/span 或 ROM |
| `LENGTH-001` | record payload 修改長度契約 | `partial-confirmed` | 相同 byte length：record/decoded stream 層可原地保留 offset；zero padding：blocked，因 `0x0000` 是 terminator；變長：需 resource rebuild／後續 jump relocation，尚無 builder | 先以相同 byte length 做最小 translation batch；未知 padding／font width 維持 blocked |
| `LAYOUT-001` | static record／layout contract audit | `confirmed`（bounded static） | `tools/audit_layout.py` 驗證 361/361 source re-encode、最大 36-byte／18-code-unit payload、`0x0308`／`0x0000` boundary，以及 `0x0001/2/3/6`、`0x0308/9/a` opcode／opaque 計數；record-contract aggregate SHA-256 `9aebe71ca654f735b41c913c08b79875f04b9b164a9c024373389b53dd70191e` | 未證實 line/page/wait、glyph width／行數、padding 或完整 container；只允許同 byte length 的 record-level 修改 |
| `RUNTIME-001` | mGBA boot snapshot 是否能直接證實文本渲染路徑 | `blocked` | 一次性 mGBA 0.10.5 GDB snapshot 讀到 `PC=0x03003652`、`DISPCNT=0x1140`、`BG0CNT=0x0088`、`KEYINPUT=0x03ff`；沒有文字 ROM-to-VRAM match | 不再嘗試 port shim；待有可重現 scripting/headless 路徑或明確 debug 入口再開 runtime |
| `RUNTIME-002` | mGBA scripting/headless 文本偵察 | `blocked` | 已安裝 CLI 不接受 `--script`；未保留未驗證的 GUI／GDB 實驗工具 | 先解決工具能力與可重現入口，否則維持靜態候選狀態 |
| `RUNTIME-003` | 共用 `core/gba` 標準 capture 是否能取得 B3CJ live RAM／VRAM／OAM | `blocked` | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s core/gba/test -v` 的 6 項測試通過；B3CJ 自有 mGBA process 的 `-C ports.qt.gdbPort=25352` 未建立 listener，2345 已由其他 session 使用；一次重用 `/private/tmp` redirect dylib 也未建立 25351。沒有產生新的 raw dump | 待有不碰其他 session 的可用 GDB port 或明確 debug 入口，再用 `core/gba/capture_runtime.py`；不重寫遊戲專屬 client |
| `RUNTIME-004` | M2.3 以獨立高位 port 取得 live palette／writer／VRAM/OAM 證據 | `blocked` | 先以 bind preflight 證實 `24387` 空閒；只載入本作 POC ROM 的 PID `26484` 執行 `-g -C ports.qt.gdbPort=24387`，`lsof -p 26484` 證實實際 listener 是該 PID 的 `*:2345`，`24387` refused；透過自有 `2345` 執行 core capture，但 `qSupported:multiprocess+` retry 後 timeout。已停止 PID，兩 port 事後均無 listener，沒有 runtime summary／raw dump | 不再把 `ports.qt.gdbPort` 當 CLI port shim；待有可重現、互不干擾的 runtime 入口，才補 palette、writer destination、VRAM/OAM layout 與畫面 glyph 可讀性證據 |
| `RUNTIME-005` | M2.4 使用 `gdb.port` 的本作專屬 fresh process／GDB handshake | `blocked` | 兩次獨立 bind preflight 分別確認 `24763`／`24764` 空閒；GUI PID `29811` 以 `-C gdb.port=24763` 啟動但無 listener，headless binary 以 `-C gdb.port=24764` 直接輸出 `Debugger: Couldn't open socket`；兩個自有 process 均已停止。`tools/runtime_m2_4.py` 對釋放 port 以共用 client 的 `0.08s` packet delay、ACK／一次 retry 收到 `ConnectionRefusedError [Errno 61]`，沒有 `qSupported`、breakpoint／watchpoint 或 raw dump | 維持 live RAM／font cache、palette、VRAM／tilemap／OAM 與畫面可讀性 blocked；下一次只接受可實際 bind 且能完成單次 `qSupported` 的 launcher，不能把 static writer contract 升格 |
| `RUNTIME-006` | M2.6 M2.5 target 的第一輪 runtime renderer QA | `blocked`（transport-only） | clean base／target／BPS hash guard 通過；高位 port `25126` 僅見 no-listener preflight；GUI PID `50537` 立即退出且 log 為空，headless PID `50654` 輸出 `Debugger: Couldn't open socket`，兩個自有 PID 均已停止；`tools/runtime_m2_6.py` 使用 core client 的 `0.08s` delay／ACK／一次 retry，兩份 ignored diagnostic 在 connect 前回報 `PermissionError [Errno 1]`，沒有 `qSupported`、breakpoint／watchpoint 或 live memory | 不把 transport negative 解讀成 ROM／譯文失敗；下一步使用 `/private/tmp` compile-time GDB-port mGBA build，或在允許 localhost socket 的環境重跑；live cache、writer→VRAM、palette、tilemap、OAM、畫面 readable 與自然／受控 reachability 仍 unknown |
| `RUNTIME-007` | M2.7 M2.5 target transport-only retry | `blocked`（transport-only） | target／BPS static guard 通過；高位 port `25273`／`26371` 均先後無 listener；headless 與另一個 SDL mGBA binary 都輸出 `Debugger: Couldn't open socket`，兩個自有 foreground process 均已停止；`tools/runtime_m2_7.py` 的兩份 single-connection probe 使用 core client `0.08s` delay／ACK／一次 retry，在 `connect()` 前回報 `PermissionError [Errno 1]`，`qSupported=null`，沒有 consumer／VRAM／render evidence | 只在允許 localhost socket 的環境或 `/private/tmp` compile-time GDB-port mGBA build 重跑；不得把無 listener／socket policy 解讀成 ROM／譯文失敗，也不得在 transport 解鎖前新增翻譯 |
| `FONT-001` | 字型 resource、cell 格式、code-unit lookup 與 bounded identity | `confirmed`（static） | 本機 type-3 id 2 `BIT` payload file `0x14d5c6c`、glyph base `0x14d5c88`、2144×24-byte cells；`sub_0800348C` function/literal hash、table A/B、fallback 與 `gUnk_03002984 + glyph_id*0x18` 公式均重跑吻合；8 個 source Shift-JIS identity/addressing samples 分開記錄 | 以 fail-closed allocation manifest 接到最小回插 slice；palette／VRAM 仍由 RUNTIME-003 獨立處理 |
| `FONT-002` | 實際 code format 的 physical slot 掃描 | `confirmed`（static） | 11280 formula candidates、6879 strict Shift-JIS pairs、2087 mapped physical slots；全零 physical cells 28，其中未引用安全空槽 `0x845..0x85f` 共 27；非空不可尋址槽 `0x141..0x15e` 共 30，未分配 | 只允許 27 個明確空槽；zero table fallback 與 out-of-resource target 維持 blocked |
| `FONT-003` | glyph cell encoder／靜態 POC | `confirmed`（static POC） | 既有 GNU Unifont 17.0.05、固定 SHA／授權；`ec48`／`ec49` → slots `0x845`／`0x846`，table/cell 修改區域 52 bytes、實際非零 byte diff 43，static render 含 adjacent untouched `0x844`；patched ROM／PGM hash 收據見 `research/m2.2-font.md` | 未更新 ROM checksum、script container 或 runtime QA；不能稱翻譯或發布 patch |
| `FONT-004` | fail-closed glyph allocation manifest／record encoder | `confirmed`（bounded static POC） | `research/m2.3-glyph-manifest.json` 固定 B3CJ／source／font hash 與唯一 `0x845..0x85f` 範圍；`tools/encode_m2_3_poc.py` 對 `ec48`／`ec49`、兩筆 4／2-byte record 重抽 mapping／cell、record／PSI3 stream 與原 resource span 內 LZ77；summary 收到 patched ROM SHA-256 `ce99a443cfab8f84cc7f7a0319b9271ce3173dc64c488ca138696ae938460a07`，所有差異均在 manifest regions；測試另拒絕 duplicate、strict collision、hash mismatch、fallback／out-of-resource 與 capacity overrun | 仍只證實 static POC；未知 VM／排版、palette／VRAM/OAM、pointer／header／BPS rebuild 與 runtime 可讀性不升格 |
| `FONT-005` | M2.4 static writer→destination 與 changed／untouched glyph 收斂 | `confirmed`（static）／`blocked`（live） | `tools/runtime_m2_4.py` 重新驗證本機 writer／caller full SHA-256、`sub_080036F8 → sub_08002CB4` 的 `0x80` 與 `sub_0800379C → sub_080031E8` 的 `0x40` RAM/output-buffer contract；同一 POC 的 adjacent untouched `0x844` 與 changed `0x845`／`0x846` 均為 12×12／24-byte static cells | 只把 destination 稱為 RAM/output buffer；尚未取得 live argument、font cache、VRAM／palette／tilemap／OAM 或畫面可讀性，不建立 controlled reachability 結論 |
| `FONT-006` | M2.5 target glyph allocation 與 static cell build | `confirmed`（static allocation）／`provisional`（Unicode identity／live render） | `research/m2.5-batch-plan.json` 與 `tools/build_m2_5_batch.py` 固定 `ec64/ec65/ec66`→`0x847/0x848/0x849`；三個 clean table entries 均為 `0x0000`、physical cells 全零且位於 `0x845..0x85f`，target-side cell SHA-256 與 post-build lookup 可重跑；沒有採用 M2.3 `ec48/ec49` 假資料 | 只證實 static allocation／cell bytes；Unicode identity、palette、VRAM／tilemap／OAM、runtime readability 與人工字型 QA 仍 pending |
| `FONT-007` | M2.6 target／adjacent static render proof | `confirmed`（static）／`blocked`（live） | `tools/runtime_m2_6.py` 對 base／target 逐一 lookup `ec64/ec65/ec66`，確認 base=`fallback`、target=`mapped` 到 `0x847/0x848/0x849`；target cell/render hashes 可重現；adjacent glyph `0x846` base／target cell SHA-256 `9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0`、render SHA-256 `83c78b3fdc4cb9b2021552642f4a34d841b9c8e23ee7bfb7baef59082aea3759` 完全相同，M2.5 re-extract 仍為 target `1`／untouched `360` | 這是 target ROM 的 static render，不是 palette、VRAM/OAM、畫面 readable 或自然 renderer hit；runtime gate 由 `RUNTIME-006` 獨立限制 |
| `SOURCE-001` | 可供帳本使用的 bounded 日文原文表 | `confirmed`（M1.5 範圍） | `tools/extract_static.py` 對固定 ROM 可重抽 361 筆 `string_id／locale／source_text／provenance`；ignored JSONL 不 stage，tracked 文件只留 hash／offset／control token | M2.5 已在此 source table 上建立一筆受限 ledger；不把它升格為全遊戲 source coverage，廣泛批次仍需完整契約 |
| `TRANSLATION-001` | 劇情、支線、夥伴、鍛造、戰鬥、道具的大批翻譯 | `blocked` | 目前完成八筆 bounded `ai_draft` static candidate；完整 VM／排版／runtime／人工審核仍未完成 | 先完成八筆 target 的人工／字型／runtime review；停止新增同型短句，先關閉發布 gate，不把 static candidates 升格為全遊戲 |
| `TRANSLATION-002` | M2.5 resource-24 首批 zh-TW static ledger／build | `confirmed`（ledger／static contract）／`provisional`（`ai_draft` translation） | `b3cj:t2:024:0x0064` 以 `restore → work → strip` 產生 tracked ledger；source hash、14-byte／7-cell／1-line contract、`0x0308`／`0x0000` control shape、target code units、resource span 與 adjacent IDs 固定；build 後 361 筆重抽為 target `1`／untouched `360`，BPS apply byte-identical | target `這次的獎品是…` 尚未人工／術語／runtime review；只允許此一筆，下一步先完成 review，不擴大翻譯批次 |
| `LEDGER-001` | extractor source table → committed ledger 的可逆分界 | `confirmed`（bounded static） | source table 361 rows、SHA-256 `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3`；`tools/validate_ledger.py` 將 local `source_text` 暫時轉成 core `text` adapter，實際跑 restore／strip；tracked ledger 1 row、target locale `zh-TW`、status `ai_draft`，JSON values round-trip identical；embedded `source`／hash drift tests rejected | 只證明 ledger workflow；下一批仍需人工／術語／glyph／layout／runtime review，不把第一筆升格為已完成翻譯 |
| `TRANSLATION-003` | M4.1 resource-22 bounded zh-TW static batch | `confirmed`（static contract）／`provisional`（translation review） | `b3cj:t2:022:0x004e` source hash `956b323686afadc76cb837332e29e5a92db3d88a746c54f25a23d9a19b1d4f2c`；12-byte／6-code-unit、無 opaque control；`ec67/ec6c`→`0x84a/0x84b`，existing `9056/8ee8/8140` preserved；cumulative target 2／untouched 359，resource 22 compressed `493/496`，BPS 2117 bytes apply byte-identical | `劈柴新手　　` 仍 `ai_draft`，尚無人工／runtime screen review；不宣稱發布 |
| `TRANSLATION-004` | M4.2 resource-16 bounded zh-TW static batch | `confirmed`（static contract）／`provisional`（translation review） | `b3cj:t2:016:0x001e` source hash `0c7840a194483b36af7414a8e8624c93d3a3ae62e6167eb1040daaae317e33d8`；10-byte／5-code-unit、無 opaque control；existing `8c78/8d90/8149/8140` mappings preserved，無新 glyph allocation；cumulative target 3／untouched 358，resource 16 compressed `180/192`，BPS 2225 bytes apply byte-identical；resource-22 candidate `b3cj:t2:022:0x0098` 的 `500/496` capacity guard rejection 另存收據 | `警告！　　` 仍 `ai_draft`，三筆 target 尚無人工／runtime screen review；不宣稱發布 |
| `TRANSLATION-005` | M4.3 resource-25 bounded zh-TW static batch | `confirmed`（static contract）／`provisional`（translation review） | `b3cj:t2:025:0x0b6e` source hash `edfe7b0a4cfae39281960bcfeb2592b66bbd47136d6b29c1bc2082dc5cf8e2c9`；8-byte／4-code-unit、無 opaque control；`ec6d`→`0x84c`，existing `8163/8140` preserved；cumulative target 4／untouched 357，resource 25 compressed `1655/1664`，BPS 3301 bytes apply byte-identical | `嗯…　　` 仍 `ai_draft`，四筆 target 尚無人工／runtime screen review；不宣稱發布 |
| `TRANSLATION-QA-001` | M4 bounded target-side QA | `confirmed`（bounded metadata/layout）／`provisional`（human language review） | `tools/audit_translation_batches.py` 對四個 plan／ledger pair 驗證 unique stable IDs、target UTF-8 hash、`7/6/5/4` code units、`3/2/0/1` allocations、byte/layout／control contracts、allowed slots、known Simplified leak guard 與 source-bearing negative test；source hash／restore-strip 由 `validate_ledger.py` 另驗 | 只涵蓋四筆 bounded target；未涵蓋全 361 rows、完整 glossary、人工翻譯／術語一致性或 runtime screen QA |
| `REINSERT-001` | M5.1 resource 24 static directory redirect | `confirmed`（static bounded）／`blocked`（runtime） | resource 24 的原 span `1379/1392` 已無安全餘裕；POC 重導至 `0x1fbb1fc` 並保持 361 筆 record／stream byte identity，目的區 free-space guard 通過 | 可用於下一個有界 resource-24 capacity-expansion translation slice；仍未證實完整 ROM relocation policy、runtime reachability 或可發布 patch |
| `TRANSLATION-006` | M5.2 resource-24 capacity-expansion zh-TW static batch | `confirmed`（ledger／static contract）／`provisional`（translation review） | `b3cj:t2:024:0x0078` 以 `restore → work → strip` 產生 tracked ledger；12-byte／6-code-unit、無 opaque control；既有 `ec65→0x848` preserved，新增 `ec6e→0x84d`；累積五筆 target／356 untouched，resource 24 compressed `1392→1396`，target ROM SHA-256 `da3b83b5470f278f455672021e2ae87452bc92d93fdbf1126c0e994dde757cb1`，BPS 4814 bytes apply byte-identical | target `特獎　重金礦` 仍 `ai_draft`，尚無人工／術語／runtime screen review；static relocation 不代表可發布 patch |
| `REINSERT-002` | M5.2 resource 24 actual static directory redirect／repack | `confirmed`（static bounded）／`blocked`（runtime） | directory `0x17190c4` 從 payload `0x17231fc`／relative `0xa20`／span `1392` 重導至 `0x1fbb1fc`／relative `0x8a220`／span `1536`；destination zero-filled、aligned refs `0`、compressed `1396 <= 1536`；361 records 重抽、local adjacent record／glyph proof 與 BPS apply 通過 | 只證實本作單一 resource 的 static rebuild；自然／受控 consumer、VRAM／palette／screen QA、header／發布 policy 與其他 resource／alias 仍 unknown |
| `TRANSLATION-007` | M5.3 resource-24 repeated prize-header static batch | `confirmed`（ledger／static contract）／`provisional`（translation review） | `b3cj:t2:024:0x012c` 以 `restore → work → strip` 產生 tracked ledger；14-byte／7-code-unit、無 opaque control；沿用 `ec64/ec65/ec66→0x847/0x848/0x849`，無新 allocation；累積六筆 target／355 untouched，resource 24 compressed `1396→1397`，target ROM SHA-256 `2fc60cd44e2f1436dd346890755543e5a54db07ae09c382ebd35f99a2c5c86ee`，BPS 4820 bytes apply byte-identical | target `這次的獎品是…` 仍 `ai_draft`，尚無人工／術語／runtime screen review；不宣稱發布 |
| `REINSERT-003` | M5.3 multi-record use of relocated resource-24 span | `confirmed`（static bounded）／`blocked`（runtime） | 從 clean ROM 重新累積到 M5.2，再在 directory `0x17190c4` 已重導的 `0x1fbb1fc`／`0x8a220`／1536-byte span 改寫第二筆 record；1397 bytes <= 1536，五筆先前 target 對 M5.2 byte-identical，local adjacent records／glyph 與 clean byte/render identical，361 records re-extract 通過 | 只證實本作單一 relocated resource 的兩筆 static rewrite；其他 resource／alias、自然／受控 runtime、palette／VRAM／screen QA、header／發布 policy 仍 unknown |
| `TRANSLATION-008` | M5.4 resource-24 lottery-question static batch | `confirmed`（ledger／font／static contract）／`provisional`（translation review） | `b3cj:t2:024:0x0886` 以 `restore → work → strip` 產生 tracked ledger；14-byte／7-code-unit、無 opaque control；`ec6f→0x84e` 的 `嗎` 是唯一新增 glyph，existing `ec65/9776/928a/8148/8140` preserved；累積七筆 target／354 untouched，resource 24 compressed `1397→1406`，target ROM SHA-256 `0ac699421df123737d6039d65b6a139819c78bab44bd17af7dadd18ac731fc0a`，BPS 4854 bytes apply byte-identical | target `要抽獎嗎？　　` 仍 `ai_draft`，尚無人工／術語／runtime screen review；不宣稱發布 |
| `TRANSLATION-009` | M5.5 resource-24 third repeated prize-header static batch | `confirmed`（ledger／static contract）／`provisional`（translation review） | `b3cj:t2:024:0x01f0` 以 `restore → work → strip` 產生 tracked ledger；14-byte／7-code-unit、無 opaque control；沿用 `ec64/ec65/ec66→0x847/0x848/0x849`，無新 allocation；累積八筆 target／353 untouched，resource 24 compressed 維持 `1406`，target ROM SHA-256 `acfb3587a8217bf4ea444daf25f32c0947998a9203ee874db5006d7b6b016db6`，BPS 4856 bytes apply byte-identical | target `這次的獎品是…` 仍 `ai_draft`，尚無人工／術語／runtime screen review；不宣稱發布 |
| `REINSERT-005` | M5.5 third repeated record in relocated resource-24 span | `confirmed`（static bounded）／`blocked`（runtime） | 從 clean ROM 重新累積到 M5.4，再在 directory `0x17190c4` 已重導的 `0x1fbb1fc`／`0x8a220`／1536-byte span 改寫第三筆 record；1406 bytes <= 1536，七筆先前 target 對 M5.4 byte-identical，local adjacent records／glyph 與 clean byte/render identical，361 records re-extract 與 BPS apply 通過 | 只證實本作單一 relocated resource 的三筆 static rewrite；其他 resource／alias、自然／受控 runtime、palette／VRAM／screen QA、header／發布 policy 仍 unknown |
| `REVIEW-001` | M5.5 後既有八筆 target consistency review | `confirmed`（bounded static metadata）／`provisional`（人工語意／術語） | [`research/m5-static-review.md`](m5-static-review.md) 逐筆固定八個 stable ID、target hash、單行／byte-length、control／glyph／adjacent contract；七筆 wording 可維持 provisional，`重金礦` 維持 `blocked_external_lookup`，全部仍為 `ai_draft` | 不新增同型 target；需人工語意／術語／字型／版面核准後才可改 status |
| `RUNTIME-008` | M5.5 後 compile-time fixed-port SDL runtime transport | `blocked`（transport-only） | `/private/tmp/mgba-source.B4BE9x` revision `afd6f14eaf8bd35214ed3fb9dc69a92bfc3877a9` 的 dirty `GDBStubListen(...,2346,...)` build；binary SHA-256 `08c8b810bf1d0b279c8e3839ab56950ae5c61fe57928d122de3eeea66048d9bf`；2346 preflight 無 listener，fresh B3CJ clean ROM foreground launch 輸出 `Debugger: Couldn't open socket`，session handle `38665` 由本 session Ctrl-C 停止，事後無 listener；無 qSupported／consumer／VRAM evidence | 不重試相同 bind；待允許 localhost socket 的環境或不同 transport implementation，維持 live cache／palette hardware／tilemap／OAM／screen blocked |
| `RENDER-001` | static writer → DMA → VRAM character destination／palette shadow（initial） | `confirmed`（static）／`blocked`（live） | [`tools/audit_static_render_destination.py`](../tools/audit_static_render_destination.py) 初版以 8 個 local function hashes、9 個 literal guards、csm3 commit `7e388ac` 交叉驗證 writer／queue／`0x06010000` 與 palette shadow；後續 palette hardware destination 由 `RENDER-002` 補證 | 初版未包含 palette hardware copy；tilemap／OAM、live cache、自然 reachability、VRAM readback／screen readability 仍 unknown |
| `RENDER-002` | static palette shadow → hardware palette DMA destination | `confirmed`（static）／`blocked`（live） | audit v2 以 10 個 local function hashes、10 個 literal guards、csm3 commit `7e388ac` 交叉驗證 `sub_08001C00 → sub_08010CD4 → sub_08006BA4`：source `gUnk_03005960+0x400 = 0x03005D60`，destination `0x05000000`，length `0x400` bytes；report SHA-256 `2446c1d64c248d74f154715568e6f82040cd630852d6cc8c068ba5a78fccccd2` | 只證實 static palette hardware destination；沒有 live palette readback、tilemap／OAM、consumer／VRAM hit 或 screen readability，不升格為 runtime QA |
| `REPO-001` | 本作 path-limited milestone commit | `blocked`（workspace permission） | 只執行 `git add -- games/summon-night-craft-sword-3/`；`.git/index.lock` 當時不存在，Git 仍回報 `Unable to create .../.git/index.lock: Operation not permitted`。沒有 alternate index、commit-tree、廣泛 stage、reset、checkout 或 stash；目前 `git diff --cached --name-only -- games/summon-night-craft-sword-3/` 為空 | 待 workspace 允許建立 index lock 後，先核對 staged scope，再以 JohnnySun 作者做 `git commit --only`；不影響已完成的本作測試與 static evidence |

## 第一個可重現檢查

對使用者提供的 ignored 日版 ROM 執行：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py --strict \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba
python3 games/summon-night-craft-sword-3/tools/scan_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/static-report.json
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/extract_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --verify-roundtrip
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/inspect_font.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --summary-output games/summon-night-craft-sword-3/work/m2.2-font-summary.json
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/encode_m2_3_poc.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --manifest games/summon-night-craft-sword-3/research/m2.3-glyph-manifest.json \
  --font-source vendor/fonts/unifont/unifont-17.0.05.hex.gz \
  --output games/summon-night-craft-sword-3/work/m2.3-poc.gba \
  --summary-output games/summon-night-craft-sword-3/work/m2.3-poc-summary.json \
  --render-output games/summon-night-craft-sword-3/work/m2.3-poc.pgm
```

`--strict` 會把 game code、header checksum、size、CRC32 與公開 reference SHA-1 一起作門檻。這次本機 readback 的 SHA-256 是 `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d`；若其他 clean dump 不同，先保留完整 hash 與差異，不修改 ROM 或用補丁檔冒充來源 ROM。`static-report.json` 是 ignored 產物，只提交工具與本帳本的摘要。

本次完整 ignored 靜態報告的 SHA-256 為 `cefdd9e0d8197b9642976ce976538a04d456d173d4837c02f6016a46a4ae0aed`；報告由上述 scanner 直接重建，不把報告或其中任何原始 bytes 加入 Git。

靜態掃描明確有界：Shift-JIS-shaped run 預設只掃 halfword alignment `0`、至少 8 個 units、最多保存 32 筆；LZ77／RLE 各最多嘗試 2048 個 header、展開上限 `0x40000`。因此「沒有候選」也不能視為全 ROM 證明；本次結果只足以把上述 offset 列為候選。

M2.1 extractor 的固定收據是 `records=361`、resource IDs `9,10,11,12,14,15,16,17,18,19,22,24,25`；ignored JSONL SHA-256 為 `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3`。`--verify-roundtrip` 收到 `32092` decoded stream bytes、source re-encode `361/361`、opaque tokens `203`、rejected marker `1`，original／encoded aggregate SHA-256 同為 `6fda79e61316e3e941e72bad156206bb855a352c546f95d3c1dba2a474025706`。此輸出含日文 `source_text`，只可存在被 ignore 的 research 路徑，不得 stage；完整控制碼、opaque 與 length-contract 收據見 [`research/m2.1-control-roundtrip.md`](m2.1-control-roundtrip.md)。

M2.2 font inspector 的固定收據是 type-3 resource `id=2`、BIT glyph base
`0x14d5c88`、`slots=0x860`、`cell=0x18`、strict mapped physical slots `2087`、
safe blank unreferenced slots `27`（`0x845..0x85f`），以及 source corpus
`records=361`／`unique_double_byte_units=382`。它也會拒絕未吻合 B3CJ identity、
reviewed csm3 function hash 或 lookup literal 的輸入；完整 samples、POC 與未知項目見
[`research/m2.2-font.md`](m2.2-font.md)。

M2.3 encoder 的固定收據是 `allocations=2`、`records=2`、`changed_bytes=1753`、
resource compressed sizes `485/496` 與 `1652/1664`，font mapping／cell、record／
PSI3 stream 均 byte-identical；manifest／測試／runtime 收據見
[`research/m2.3-poc.md`](m2.3-poc.md)。

M2.4 的固定收據是兩輪 `gdb.port` fresh process：`24763` 的 GUI PID `29811` 無
listener，`24764` 的 headless binary 輸出 `Debugger: Couldn't open socket`；兩輪
均停止自有 process，diagnostic 對釋放 port 收到 `ConnectionRefusedError`。共用
GDB client 的 `qSupported` 未送達，故沒有 live coverage。static fallback 只確認
writer→RAM/output-buffer 的 `0x80`／`0x40` contract、full function hashes，以及
changed `0x845/0x846` 和 adjacent untouched `0x844` 的 cell evidence；不代表
VRAM／palette／OAM 或畫面 render。詳見 [`research/m2.4-runtime.md`](m2.4-runtime.md)。

M2.5 的固定收據是 resource-24 一筆 target：`b3cj:t2:024:0x0064`、source hash
`c10caff6b389dc1506d1879cdac4e21111ead7eb8b41e05eca6aed3d73873ddc`、target UTF-8
hash `ce6e829d970a7d1d4a0330637244dca64b0412b61ea88c4bdaa1687df6c0e2b0`，以及
`ec64/ec65/ec66`→`0x847/0x848/0x849`。`build_m2_5_batch.py` 先產生 ignored source
adapter，再經 core ledger restore／strip；static build 重新抽取 361 筆（target
`1`、untouched `360`），resource 24 compressed/span `1379/1392`→`1392/1392`，
changed bytes `1397`。target ROM SHA-256 為
`da9c99426bf80c18729256a694ce6e499eab6d036fe26887908b8cb44cdf5b16`，BPS 為
`1543` bytes、SHA-256 `42618b4afffed33600f3f8f73b3e3f6bea3f7aa9ba8c74e5016121f9f7ec6e5b`，
apply 後與 target byte-identical。完整 plan／ledger／build 邊界見
[`research/m2.5-batch.md`](m2.5-batch.md)；runtime、人工 review 與發布資格仍 pending。

M2.6 的固定收據是 target `b3cj:t2:024:0x0064`、clean／target／BPS hash guard、
target `1`／untouched `360` re-extraction 與 adjacent glyph `0x846` base／target
cell/render equality；三個 changed static glyph 是 `ec64/ec65/ec66`→
`0x847/0x848/0x849`。兩輪 fresh launcher 使用 port `25126`：GUI PID `50537`
立即退出，headless PID `50654` 輸出 `Debugger: Couldn't open socket`，兩個自有 PID
均已停止且事後無 listener。`tools/runtime_m2_6.py` 的兩份 ignored diagnostic
都在 connect 前 blocked，沒有 `qSupported` 或 live coverage；完整 attempt／error／
下一個 compile-time-port 方案見 [`research/m2.6-runtime.md`](m2.6-runtime.md)。

M2.7 的固定收據是同一 target／static proof 上的兩輪 transport retry：`25273` 使用
`/private/tmp/atlantis-mgba-headless-build2/mgba-headless`，`26371` 使用
`/private/tmp/mgba-smt2-sdl-build/sdl/mgba`；兩輪啟動前後均無指定 port listener，
launcher 都輸出 `Debugger: Couldn't open socket`，自有 foreground process 均已停止。
PTY wrapper 未暴露 child OS PID，report 保留 `process_pid=null`，不以 session handle
冒充 OS PID。`tools/runtime_m2_7.py` 的兩份 ignored report 都在 `connect()` 前收到
`PermissionError [Errno 1] Operation not permitted`，`qSupported` 沒有送達；因此
沒有 natural／controlled consumer hit、font cache、writer→VRAM、palette、tilemap、
OAM 或畫面 render 結果。完整命令與 safe alternatives 見
[`research/m2.7-runtime.md`](m2.7-runtime.md)。

M2.8 的固定收據是 `tools/audit_layout.py` 對 clean B3CJ ROM 的 static contract
audit：13 個含 record resource、361 筆 record、11 個 payload groups，resource
`9`／`10` 為 resource `11` 的 zero-span alias；positive spans 不重疊，source
re-encode 為 `361/361`。record-contract aggregate SHA-256 是
`9aebe71ca654f735b41c913c08b79875f04b9b164a9c024373389b53dd70191e`。這只確認
pointer／record 邊界與結構計數；opaque control、line/page/wait、glyph width、
變長／padding、完整 compressed rebuild 與 runtime layout 仍 unknown。完整收據見
[`research/m2.8-layout.md`](m2.8-layout.md)。

## 外部資料索引

- [Data Crystal 遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650)：B3CJ、容量、CRC32 與 header checksum 的候選 metadata。
- [Data Crystal TBL oldid=53006](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006)：主日文字型的公開 code-table 線索；已與本機 bounded record 交叉驗證，但不是完整原文來源。
- [csm3 固定 commit](https://github.com/jiangzhengwenjz/csm3/commit/7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2)：可供控制流／資料結構研究的公開工程參考；其 build/reference hash 與本機 ROM 分開記錄，固定 checkout 的 root license 狀態見 [`research/external-sources.md`](external-sources.md)。
- [臺灣繁體 Wikipedia 條目](https://zh.wikipedia.org/wiki/%E5%8F%AC%E5%96%9A%E5%A4%9C%E9%9F%BF%E6%9B%B2_%E9%91%84%E5%8A%8D%E7%89%A9%E8%AA%9E_%EF%BD%9E%E8%B5%B7%E6%BA%90%E4%B9%8B%E7%9F%B3%EF%BD%9E)：標題與部分角色名稱的既有中文寫法參考。
- [巴哈姆特流程攻略](https://forum.gamer.com.tw/G2.php?bsn=5499&lorder=1&parent=584&sn=578)：本作流程與專有名詞的社群用語交叉參考；不把攻略內容當成 ROM 原文。

既有英文／中文 patch 只可用來核對工程方向、已知版號或 bug 線索；不可把 patch 內的翻譯腳本直接當作日文來源，也不可把 ROM、完整原始腳本或未授權字型帶進 Git。

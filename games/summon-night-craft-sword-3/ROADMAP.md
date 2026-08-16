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

本里程碑的靜態報告只保留 offset、長度、計數、引用與 hash。共用 `core/gba` client／capture／renderer 的 6 項測試已通過；一次性的 mGBA boot snapshot 已記在研究帳本，但 B3CJ capture 仍受其他 session 的 2345 與 alternate-port listener 阻塞，不再重試 port shim，也不把 runtime 實驗工具納入本作工具集。

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

## M2：文本與字型格式

- [~] 定位已確認的 `PSI3` script resource、bounded text record 與部分 VM control shape；仍需把劇情／支線／夥伴／鍛造／戰鬥／道具群組完整分類。
- [~] 已確認 type-2 pointer、GBA LZ77、script bytecode、record-level Shift-JIS 與部分 expression／control width；未知 VM opcode、完整換行／分頁語意仍待命名。
- [x] 定位字型資料與渲染器；分開驗證 glyph addressing 與 glyph identity（static M2.2 範圍）。
- [~] palette、writer output、VRAM/OAM layout 與 live screen 仍待 runtime 交叉驗證。
- [ ] 確認字串 ID、指標、換行、控制碼、字寬／行數上限與未修改內容的回插契約。
- [ ] 以 ROM-to-VRAM byte match、已知畫面內容或全語料庫上下文重讀交叉確認解碼。

## M3：原文表與可逆試驗

- [~] 由遊戲專用 decoder 產生本機 ignored `research/summon-night-craft-sword-3-decoded.jsonl`，每行含 `string_id`、`locale`、`source_text`、structured controls、length contract 與 `provenance`；尚未建立可提交 translation ledger。
- [ ] 先選一個可達、短且有明確結構的 UI／道具／戰鬥批次，不一次處理全遊戲。
- [ ] 建立本機 `work/*.jsonl`，明寫 `zh-TW`、`status`、`context`、`terms`。
- [ ] 用 `core/ledger/restore_translations.rb` 與 `strip_translations.rb` 驗證 source hash 與帳本往返。
- [ ] 只提交不帶 `source` 的 `translations/*.jsonl`，並通過 `scripts/check-repository-safety.rb`。

## M4：有限量翻譯與術語

- [ ] 依日文原文與上下文建立劇情、支線、夥伴、鍛造、戰鬥、道具的分批工作帳。
- [ ] 專有名詞以 Wikipedia zh-tw、巴哈姆特及其他獨立社群資料交叉核對；不把單一 patch 的譯名視為定論。
- [ ] 建立 `translations/glossary.zh-TW.tsv`（只收已核對術語，不放完整原文段落）。
- [ ] 逐批做字寬、行數、缺字、控制碼、簡繁混用與用語一致性 QA。

## M5：回插、BPS 與 runtime QA

- [ ] 建立本作專用 encoder／font subset／回插器；缺字、來源 hash、控制碼與長度不符時 fail closed。
- [ ] 從重建 ROM 重新抽取，確認未修改字串與目標翻譯均吻合。
- [ ] 生成 BPS，套用後做 byte-for-byte round-trip，記錄 target CRC32、patch size、SHA-256。
- [ ] 以 mGBA 測試實際可達的劇情／支線／夥伴／鍛造／戰鬥／道具畫面，保留未測試範圍。
- [ ] 只有完成上述收據後，才評估 zh-TW 發布。

# 《超級機器人大戰 D》工作路線圖

## M0：來源與安全邊界

- [x] 只使用日版候選 ROM 做本機偵察。
- [x] 建立 `roms/base/`、`research/`、`tools/`、`translations/` 分工。
- [x] 確認新遊戲翻譯一律走 source／working／ledger 分離，不把原文寫入可提交
  的 translation record。

## M1：文字系統逆向

- [x] ROM 標頭、版本、CRC32、SHA-256、header complement。
- [x] 結構性 Shift-JIS、4-byte ROM pointer、BIOS compression、BIOS SWI 初掃。
- [x] 在 `0x076000..0x082490` 確認一個 NUL 結尾的嚴格 Shift-JIS 靜態文字池，
  並以 4-byte 絕對 pointer 命中做靜態交叉核對。
- [x] 完成 bounded mGBA runtime 邊界檢查：ROM entry 與 VRAM transfer 有陽性命中，
  對文字池首字的 read watchpoint 在 bounded boot window 陰性；此結果不宣稱
  renderer／字型已證明。
- [x] M1.5 完成 bounded pointer-caller／literal-pool 分類，並以 `0x0800f49a` ->
  `0x08007e04` 確認一個真實 source-byte consumer；反組譯與受控 runtime 亦走通
  `0x08008724` -> `0x080085fc` -> glyph-base arithmetic -> `0x08008650`。
  自然畫面觸發與完整 renderer QA 仍待完成，不能把 bounded trace 擴張成全遊戲覆蓋。
- [x] M1.6 以 slot watchpoint 確認 `0x08014e8c -> 0x080083a0` initializer、
  `0x08008456`／`0x08008462` slot writer 與兩個 nonzero ROM resource base；在
  base 已初始化後，以 `0x0807b3fc`／`0x0807b380` 的 strict source context 確認
  `ラ`／`移` 兩條 code unit -> glyph bytes -> tile writer output chain。
- [ ] 由自然畫面／queue 狀態擴大確認文字 renderer／decoder 的呼叫鏈覆蓋。
- [ ] 完整定位文本區與字串分區：話數、分支、機體／駕駛員／武器／精神、戰鬥
  對話及 UI；目前只完成靜態池的局部分類。
- [x] M1.6 已用 strict source context 分別證明兩個 bounded sample 的「glyph
  addressing」與「glyph identity」，不能以字符表位置猜測 Unicode 身分。
- [x] M1.7 完成 `0x08008724` 的 bounded 靜態 token／NUL terminator／two-byte
  窄寬 glyph class 分類（無已證明的 single-byte glyph path），並在 2325 筆 source
  corpus 上驗證 no-op byte identity；同時盤點
  resource stride、空白／不可達 slot 與保守容量，建立兩筆同長度 fail-closed POC。
  newline 與未知 token 維持 opaque，尚未開始翻譯或修改 ROM。
- [x] M1.8 將窄字 mode `0x080085fc` 反組譯為可重現的 544-slot formula，保留
  3 個 blank-but-referenced slot，從完整 corpus 收斂出 165 個安全空槽；確認
  8×12／12-byte packing，使用固定 hash／license 的 GNU Unifont T-source 建立
  fail-closed allocator，並完成一筆同長 `zh-TW` static glyph POC。寬字新槽容量
  為 0；target／相鄰 re-read、BPS create/apply 已通過，patched runtime 尚 pending。
- [x] M1.9 完成 `string_id=526424` 的 target／相鄰 static metadata、NUL／width
  gate、runtime QA 工具與純測試；以自己的 port `24567` 完成兩次 clean restart
  嘗試並記錄 GDB single-connection transport negative。既有 M1.6 controlled
  consumer positive 保留為獨立證據，沒有冒充 patched target 畫面 QA。
- [ ] M1.9 patched target runtime：在新的獨立 mGBA process／port 重新捕捉
  slots `543/542` 的 writer destination、cache／VRAM hash 與相鄰 record；自然
  menu／queue、newline branch 仍須分開驗證。已嘗試新 port `24731`：launcher 成功，
  但 GDB socket／approval transport 未能提供 probe，維持 `not_observed`。另一次
  自有 patched process `2346` 通過 font-base guard 卻在 target loop 只得到
  `codepage=1/glyph=1`（預期 2），fail-closed；後續 trace 在 initializer 前
  `S04/PC=0x4`，writer／tile／screen proof 仍 pending。
- [x] M1.14 對另一個獨立 port `2346` trace 做精確 source-consumer gate：patched
  ROM hash／single connection／兩個 nonzero font base 通過，但 requested source
  `0x08080858` 的 codepage event 指向 `0x02018368`、unit `0x628D`，不是 requested
  pointer，且只見 1 個 codepage／0 個 narrow glyph；raw complete event 不升級成
  target proof。工具現在要求 observed source pointer 與 unit count 同時吻合，摘要在
  `research/m114-runtime-boundary.json`；下一次需用 caller/callsite breakpoint 或
  已驗證 callee-entry state。
- [x] M1.15 完成已知 consumer 的 bounded static callsite audit：只在
  `0x08000000..0x08076000` 檢查 direct Thumb BL／BLX 與 PC-relative literal，結果
  均為 `0`；register-indirect dispatch 未命名，`runtime_caller_required=true`。
  `m115_caller_probe.py` 的 entry breakpoint 工具與測試已建立，但本輪執行前 approval
  transport 被拒絕，沒有把它記成 runtime positive；摘要在
  `research/m115-consumer-callsite.json`。
- [x] M1.10 對 2325 筆 source record 完成 NUL／ordering／overlap／ROM equality
  audit、opaque／unaligned 分布、line-width 統計與 `0x0807B3FC` 16-record bounded
  no-op cohort；unknown token 與 newline semantics 維持 opaque／未命名。
- [x] M1.11 對 `0x08008724..0x08008A0C` 完成 bounded layout instruction gate，固定
  NUL／two-byte／8-or-12px／tile allocation 公式與 mode branch 邊界；speaker、
  newline、完整多行與 branch mode 語意仍維持 opaque。
- [x] 建立全語料 source-safe structural inventory：2325/2325 strict source／NUL／
  no-op 通過；939 筆全窄 glyph-only、833 筆混合、417 筆全寬、136 筆
  opaque／unaligned。這是可重現的格式分區，不是話數／劇情語意分區；摘要在
  `research/m4-corpus-inventory.json`，工具只輸出 hash／offset／count metadata。
- [ ] 定義控制碼、終止符、換行、說話者、最大寬度／行數與分支邊界。
- [ ] 用自然畫面或更多獨立語料上下文擴大重讀確認解碼結果；M1.6 的兩個 sample
  仍是同一受控 consumer path 的最小證據。

## M2：可審核翻譯資料

- [x] 產生並以 strict ROM checker 驗證本機 ignored
  `research/super-robot-taisen-d-decoded.jsonl`（2325/2325）。
- [x] 以 `restore_translations.rb` → ignored working record → `strip_translations.rb`
  完成一筆 source-safe、同長度的 M1.8 static `ai_draft` ledger POC；這不是批量
  翻譯，也不代表術語或完整 layout 已定稿。
- [x] 建立 `translations/glossary.zh-TW.tsv`，以 Wikipedia zh-tw、RoboInfo、
  巴哈姆特與日文攻略頁交叉核對 17 個 bounded terms；12 個術語通過雙來源 hash
  provenance，4 個短名／標點衝突維持 `deferred_conflict`，另有 1 個 UI term 為
  `provisional`，不先回插。可重跑
  `tools/m2_glossary_audit.py`，摘要在 `research/m2-glossary-audit.json`；TSV
  不保存完整日文原文。
- [x] 完成第一個可達且邊界明確的 UI 小批次：`string_id=526432` 兩窄字、NUL、
  16px line width、無 control token，以 `ai_draft`「存在」建立 static glyph／
  adjacent／BPS gate；精神指令 `509548` 因 source wide glyph 被 fail-closed 拒絕，
  沒有使用寬字新槽。
- [x] 對 M2 batch-1 使用 `restore_translations.rb` 產生 ignored working record，
  再用 `strip_translations.rb` 產生 source-safe ledger；tracked ledger 不含 source。
- [x] M2 batch-1 通過 ledger schema、repository safety、glossary provenance、字寬／
  行數與控制碼 QA；全語料／全場景批次仍未宣稱完成。

## M3：回插與 QA

- [x] 建立 bounded 遊戲專屬窄字 codepage／Unifont 8×12 子集／global allocator／
  static reinsertor：`tools/m3_reinsert.py` 可合併多筆 source-safe working ledger，
  共用重複 glyph、拒絕 source mismatch／wide／opaque／變長／slot collision／overlap；
  contract 摘要在 `research/m3-reinsert-contract.json`。寬字、未知控制碼與完整 corpus
  encoder 仍未完成。
- [ ] 重抽取 rebuilt ROM，確認未修改字串與預期譯文一致。
- [x] M3 bounded re-extraction comparator 已建立並對兩筆 static POC 驗證；完整
  rebuilt-ROM／全語料 extraction 仍待完成。
- [x] M3 bounded static POC 產生 BPS、套用 clean ROM 並完成 byte-for-byte round-trip；
  full rebuilt-ROM extraction／全語料 BPS 仍待完成。
- [ ] 以 mGBA 覆蓋標題、選單、分支入口、話間／戰鬥對話、機體／駕駛員／武器／
  精神指令等核心畫面；未測項目要列明，不從靜態結果推定通過。

## M4：完整翻譯與發行驗收

- [ ] 以可達 caller／自然畫面證據完成靜態池的話數、分支、UI、機體／駕駛員／
  武器／精神與戰鬥／話間文本分區；未知 pointer、opaque token 與池外文本維持
  可追蹤的未確認狀態。
- [ ] 證明完整控制碼、newline、speaker、最大行寬／行數與 branch layout，或以
  明確 fail-closed contract 排除未證明 record；不得以 M1.11 的 bounded width 外推。
- [ ] 完成寬字 codepage／resource 策略：只能重用已證明 Unicode identity 的既有
  slot，或以可回插、可重抽取、runtime 驗證的資源擴容；不得把寬字新槽容量 0
  偷換成可翻譯容量。
- [x] M4 bounded wide reuse audit 完成 2325 筆 source context 的 743 個一對一
  Unicode→code-unit→既有 slot metadata（3983 occurrences），並確認既有 wide
  slot payload 已初始化；其中 `0xDA88`／`U+79FB` 有 M1.6 runtime positive，
  其餘 742 筆維持 static-only。新增寬槽與未在 map 的 target 仍 fail-closed；完整
  font expansion／全場景 proof 尚未完成，摘要在 `research/m4-wide-reuse-audit.json`。
- [x] M4 bounded wide reuse contract 將既有 743-entry map 收斂成可執行 policy：只接受
  已映射且已初始化的 existing slot，unknown target、new wide slot 與 font expansion
  一律 reject；runtime confirmed 仍只有 1，完整 wide resource strategy 尚未完成。
  摘要在 `research/m4-wide-reuse-contract.json`。
- [x] M4 bounded source provenance join 重用既有 pointer-caller report，確認 4,947
  refs／915 literal candidates 中 609 個 exact source candidates 對應 370 筆 record，
  並按 structural partition 保存 caller／literal confidence 與 ID hash；semantic
  partition 仍明確標為 `unclassified`，不把 pointer 命中外推成話數／UI／劇情。
- [x] M1.12 bounded semantic/caller boundary 重用同一 pointer report，不做新掃描；
  609 exact candidates／370 records 形成 123 個 caller cohorts（輸出前 32），與
  2325 structural partition、2 個 controlled runtime positive 的 overlap/hash 分欄。
  story／branch／battle／unit／UI 語意仍 `unconfirmed`，newline／speaker／最大寬度
  也不外推；摘要在 `research/m112-semantic-caller-boundary.json`。
- [x] M4 full-corpus fail-closed gate 完成 2325/2325 strict source／NUL／token no-op
  重讀；12 筆 ledger 全在窄字 accepted subset，其餘 927 筆窄字尚未翻譯、833 筆混合、
  417 筆全寬、136 筆 opaque／unaligned 明確拒絕。`full_encoder_status` 維持
  `fail_closed_subset_only`，不宣稱完整語意 encoder。
- [x] M1.13 bounded full-encoder contract 完成：重用 28 個窄字 allocation 與 743 個
  strict source-context wide identity，核對 ROM／Unifont／license hash、code-unit→slot
  公式與一對一 collision；12/12 ledger source hash／同長 encode、2325/2325 source
  token no-op 通過。只有 1 個 wide identity 有 bounded runtime confirmation，742 個
  static-only wide 與 wide new slot capacity 0 維持 reject；`full_semantic_translation`
  仍為 `false`。摘要在 `research/m113-full-encoder-contract.json`。
- [ ] 在上述 gate 後建立完整 source-safe `zh-TW` ledger，所有專有名詞先通過
  glossary provenance；每筆翻譯保留 restore／working／strip 可重現鏈，opaque／
  變長／缺字／超寬 record fail-closed。
- [x] M4 bounded UI batch-2 完成一筆全窄、兩 unit、16px、NUL、無 control 的
  `string_id=512228` `ai_draft`「沒有」；依 restore→working→strip 建 ledger，並與
  M1.8／M2 三筆合併驗證 duplicate codepoint reuse（新增 unique glyph 0）。這是
  static POC，不代表全語料翻譯或 runtime screen QA。
- [x] M4 bounded UI batch-3 完成 5 筆全窄、3 unit、24px、NUL、無 control 的一般
  UI labels；seed ledger 由 source shape 計算實際 width，5 筆與前批合併為 8 records、
  15 unique narrow allocations，`：` codepoint 跨 record 共用。static BPS／round-trip
  通過；完整批次與 runtime QA 仍未完成。
- [x] M4 bounded UI batch-4 完成 3 筆全窄、6／7 unit、48／56px、NUL、無 control 的
  UI／status labels；依 restore／strip 建立 source-safe `ai_draft` ledger，與前批合併
  為 11 records／26 unique narrow allocations。static BPS／round-trip 通過：
  source 2325/2325、target 11/11、untouched 2314/2314、outside allowed ranges equal；
  runtime screen 仍 pending，寬字新槽仍為 0。摘要在 `research/m4-ui-batch4.json`。
- [x] M4 bounded UI batch-5 完成 `516324` 一筆全窄、8 unit、64px、NUL、無 control 的
  UI prompt；與前批合併為 12 records／28 unique narrow allocations，static BPS／
  round-trip 通過：source 2325/2325、target 12/12、untouched 2313/2313、outside
  allowed ranges equal。runtime screen 仍 pending；摘要在 `research/m4-ui-batch5.json`。
- [ ] 完成全語料 encoder／回插、重抽取 byte round-trip、BPS create/apply，並以
  target／untouched／font／ROM hash 及 changed-range audit 證明沒有旁改。
- [ ] 以獨立 mGBA 覆蓋核心流程與 translated records，記錄自然／controlled 分欄、
  screen／VRAM／writer evidence；所有未達成畫面保留 pending，不宣稱發行完成。
- [ ] 最終通過 game tests、core/gba tests、strict source、ledger schema、AST、
  repository safety，並以 path-limited JohnnySun commit 保存本作全部可提交成果。

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
  menu／queue、newline branch 仍須分開驗證。
- [x] M1.10 對 2325 筆 source record 完成 NUL／ordering／overlap／ROM equality
  audit、opaque／unaligned 分布、line-width 統計與 `0x0807B3FC` 16-record bounded
  no-op cohort；unknown token 與 newline semantics 維持 opaque／未命名。
- [x] M1.11 對 `0x08008724..0x08008A0C` 完成 bounded layout instruction gate，固定
  NUL／two-byte／8-or-12px／tile allocation 公式與 mode branch 邊界；speaker、
  newline、完整多行與 branch mode 語意仍維持 opaque。
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
  巴哈姆特與日文攻略頁交叉核對 16 個 bounded terms；12 個術語通過雙來源 hash
  provenance，4 個短名／標點衝突維持 `deferred_conflict`，不先回插。可重跑
  `tools/m2_glossary_audit.py`，摘要在 `research/m2-glossary-audit.json`；TSV
  不保存完整日文原文。
- [ ] 先做一個可達且邊界明確的小批次：例如 UI／精神指令／一個完整對話群，
  不是整部作品一次翻譯。
- [ ] 用 `restore_translations.rb` 產生本機工作檔；完成後只用
  `strip_translations.rb` 產生可提交 ledger。
- [ ] 通過 schema、repository safety、術語、字寬／行數與控制碼 QA。

## M3：回插與 QA

- [ ] 建立遊戲專屬 codepage／字型子集／編碼器／回插器。
- [ ] 重抽取 rebuilt ROM，確認未修改字串與預期譯文一致。
- [ ] 產生 BPS，套用回 clean ROM 並做 byte-for-byte round-trip。
- [ ] 以 mGBA 覆蓋標題、選單、分支入口、話間／戰鬥對話、機體／駕駛員／武器／
  精神指令等核心畫面；未測項目要列明，不從靜態結果推定通過。

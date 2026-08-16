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
- [ ] 定義控制碼、終止符、換行、說話者、最大寬度／行數與分支邊界。
- [ ] 用自然畫面或更多獨立語料上下文擴大重讀確認解碼結果；M1.6 的兩個 sample
  仍是同一受控 consumer path 的最小證據。

## M2：可審核翻譯資料

- [x] 產生並以 strict ROM checker 驗證本機 ignored
  `research/super-robot-taisen-d-decoded.jsonl`（2325/2325）。
- [ ] 建立 `translations/glossary.zh-TW.tsv`，專有名詞先核對 Wikipedia zh-tw、
  巴哈姆特等多個社群來源，記錄分歧與採用理由。
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

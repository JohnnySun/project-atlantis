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
- [ ] 由 runtime 或反組譯確認文字 renderer／decoder 的呼叫鏈。
- [ ] 完整定位文本區與字串分區：話數、分支、機體／駕駛員／武器／精神、戰鬥
  對話及 UI；目前只完成靜態池的局部分類。
- [ ] 分別證明「glyph addressing」與「glyph identity」，不能以字符表位置猜測
  Unicode 身分。
- [ ] 定義控制碼、終止符、換行、說話者、最大寬度／行數與分支邊界。
- [ ] 用至少兩個獨立畫面／語料上下文重讀確認解碼結果。

## M2：可審核翻譯資料

- [ ] 產生本機 `research/super-robot-taisen-d-decoded.jsonl`。
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

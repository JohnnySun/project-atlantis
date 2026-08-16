# M3 event-system batch 2：custom zh-TW glyph fixed-slot round-trip

日期：2026-08-16（Asia/Taipei）

本批次完成 pool D 尚餘可辨識的 6 個 non-empty unique menu／event targets；aliases
仍由同一 pointer record 驗證，不重複建立 ledger rows。需要 custom glyph 的字形由
既有 mapping 與授權 Unifont-T gate 提供。完整日文原文、ROM、work、generated planes、
patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/event-system-batch-2.jsonl` 有 6 筆 source-free rows：D `000`、`003`、
  `008`、`010`、`013`、`021`。每筆有 source hash、`zh-TW` target、上下文、max width、
  控制碼清單和 `ai_review` 狀態；restore→strip 逐 byte 相同，schema pass，source
  fields `0`。
- D pool boundary 保持 file base `0x0D4D00`、28 entries、16 unique targets；本批次
  selected 6 unique targets，aliases 展開為 12 selected entries。未選取 records 維持
  byte-identical，pointer table 不變。
- custom-aware encoder 對 `U+8A0A`、`U+8B80`、`U+5C07`、`U+6B77`、`U+552E`、
  `U+6280` 使用 `m3-custom-glyph-map.json` 的 existing raw code units；其他字元走
  strict Shift-JIS。6 個 custom glyph plane 全部 match，selected re-extract `12/12`、
  fixed-slot `12/12`，changed bytes `360`，ROM size保持 `4194304` bytes。
- clean ROM SHA-256 為 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；
  patched／BPS-applied ROM SHA-256 均為
  `8332f030299a422b373a87790b916e9122c9ee32b62d093c1e3c02fb34d4a3dc`。
- D batch 2 BPS：`493` bytes；source CRC32 `a4a1c956`、target CRC32 `e3c08899`、
  patch CRC32 `a5138722`；BPS SHA-256
  `22efbb238ad5d0b406c7f6768fd9055881ddfdbfd04390b739a5d2ca40d5276b`。套用後與
  custom patch output `cmp` 相等。

## provisional／pending

- D pool 的 16 unique targets 現已分成 batch 1 的 9 個既有 codepage rows 與 batch 2
  的 6 個 custom-glyph rows；剩餘 1 個 unique target 是空字串 record，不猜測其語意。
- 這 6 筆仍為 `ai_review`，需自然 menu／ending 畫面核對、人工臺灣 UI 用語審核和
  custom glyph 可讀性 QA；custom raw code unit non-use 只由四池 decoded source table
  支持，不能外推全 ROM。
- 目前證明的是 selected D record／glyph-slot layer，不是完整 D pool、自然 runtime
  reachability、全遊戲字庫／版面或發布 patch。
- M2.6 以 clean 與本批 patched ROM 各做一條 title→menu bounded path；兩者均到達
  `DISPCNT=0x1F40` 的 OAM menu state，但 OAM／VRAM／composite render hash 完全相同，
  且 D／B／E formatter pipeline 全 0。因此本批次目前沒有自然 D consumer 或已翻譯
  menu 畫面 receipt，不能把三列 OAM menu 的文字 source 指派給 D:000／003／008／010／
  013／021。

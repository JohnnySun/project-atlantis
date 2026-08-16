# M3 story-event E batch 18 round-trip（2026-08-16）

本批次處理劉備臨終思緒、桃園結義誓言與安詳離世的開場結局片段
E:000／E:001。完整 source 只在 ignored ROM-derived source table／work；本文件只保存
hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:000、E:001（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077328`、`0x07738C` |
| source／target payload | 97／68、122／68 bytes；fixed-slot fit `2/2` |
| source／target lines | 4／4、5／5；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；existing B3EJ codepage，無新增 custom glyph |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `0/0` |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:000 保留臨終時對強敵、漢王朝與民生的思緒；E:001 延續桃園結義
誓言與劉備安詳離世。兩筆皆由既有 B3EJ codepage 覆蓋，沒有新增 E-specific slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `bc9b1427`。
- fixed-slot patch changed `218` bytes；patched ROM SHA-256
  `44fd11a906f6698c0c66f806a60da75280f5e49ea9f58db1e221b0333c41851a`。
- BPS `257` bytes；BPS CRC32 `42125eb4`；BPS SHA-256
  `cd3a1f0ac18c09ee84898d684cdffdacfe52bf68d403c22de39577f6e9def09e`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `44fd11a906f6698c0c66f806a60da75280f5e49ea9f58db1e221b0333c41851a`。

## Evidence boundary

E:000／E:001 與劉備臨終、桃園結義誓言及安詳離世的連續結局片段相符；公開歷史資料只作
術語背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph
cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

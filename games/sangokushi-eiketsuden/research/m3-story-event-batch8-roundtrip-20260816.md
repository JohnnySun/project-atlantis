# M3 story-event E batch 8 round-trip（2026-08-16）

本批次處理另一條結局敘事分支的 E:012／E:013。完整 source 只在 ignored
ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS
metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:012、E:013（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x07779C`、`0x077804` |
| source／target payload | 101／64、99／64 bytes；fixed-slot fit `2/2` |
| source／target lines | 4／4、4／4；target max width `13`／`12` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `4/4`；new bounded slots U+737B／U+4E82 at indices 34／35；existing U+95DC／U+570B reused |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。新增兩個 raw unit 皆通過 292-record bounded source-use non-use；
這不是 full-ROM non-use proof，也不由 slot addressing 單獨推導 Unicode identity。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `d5b570ef`。
- fixed-slot patch changed `393` bytes；patched ROM SHA-256
  `5187703988e1fd843223244b72087c381e823364b3fe51d7febb71e00eba997c`。
- BPS `490` bytes；BPS CRC32 `8c35c5ab`；BPS SHA-256
  `08d34403808810eb6dea9bdf10de5c54d146bb211c0dffd959dea5f7be0b1a6b`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `5187703988e1fd843223244b72087c381e823364b3fe51d7febb71e00eba997c`。

## Evidence boundary

E:012／E:013 是 hash-only 分組中的另一條結局敘事分支；公開流程資料只作章節／術語
背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph cache→
VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

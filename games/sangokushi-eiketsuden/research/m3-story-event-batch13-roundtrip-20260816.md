# M3 story-event E batch 13 round-trip（2026-08-16）

本批次處理劉備掌權片段的銜接與反叛退位敘事 E:022／E:023。完整 source 只在 ignored
ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS
metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:022、E:023（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077B0C`、`0x077B2C` |
| source／target payload | 29／13、97／57 bytes；fixed-slot fit `2/2` |
| source／target lines | 2／2、4／4；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `2/2`；U+4E82／U+6B64 at indices 35／26 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:022 以「人」銜接 E:021 的未完片段；E:023 保留四行敘事，`亂`
與兩次 `此` 使用已通過 source-use gate 的 E-specific slots。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `4857d6d9`。
- fixed-slot patch changed `233` bytes；patched ROM SHA-256
  `1931d2bdf048a4c3a19f8f3eab73becfa6b9f5e2a4a6602579a31c82cf484900`。
- BPS `298` bytes；BPS CRC32 `2144df1c`；BPS SHA-256
  `64e24dbd7392c4ecdb294a467eac921adcc50655679080c9f8cad1e5e6fdf4bb`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `1931d2bdf048a4c3a19f8f3eab73becfa6b9f5e2a4a6602579a31c82cf484900`。

## Evidence boundary

E:022／E:023 與劉備掌權後的反叛退位敘事分組相符；公開歷史資料只作術語背景，不能
取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph cache→VRAM／tilemap
receipt 與人工 zh-TW 終審仍 pending。

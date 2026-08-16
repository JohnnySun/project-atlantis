# M3 story-event E batch 14 round-trip（2026-08-16）

本批次處理漢朝復興／劉備短暫安定生活的延續，以及遭冷落人物片段
E:024／E:025。完整 source 只在 ignored ROM-derived source table／work；本文件只保存
hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:024、E:025（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077B90`、`0x077BEC` |
| source／target payload | 91／54、18／12 bytes；fixed-slot fit `2/2` |
| source／target lines | 4／4、1／1；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `1/1`；U+537B at index 16 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:024 延續漢朝復興與劉備安定生活敘事；E:025 保留短 fragment，
`卻` 使用已通過 bounded source-use gate 的 E-specific slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `877bc6fd`。
- fixed-slot patch changed `153` bytes；patched ROM SHA-256
  `56ac1674e2af9adb8c4c1fded7b1bead406493b6c1a9eefe35fd798af9637c6f`。
- BPS `206` bytes；BPS CRC32 `1f853700`；BPS SHA-256
  `10f35a6ced9e3f719e8a049354cd258e74884d7e6e945d81fceb8cd4763b0097`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `56ac1674e2af9adb8c4c1fded7b1bead406493b6c1a9eefe35fd798af9637c6f`。

## Evidence boundary

E:024／E:025 與漢朝復興、劉備安定生活及後續冷落片段的分組相符；公開歷史資料只作
術語背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph
cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

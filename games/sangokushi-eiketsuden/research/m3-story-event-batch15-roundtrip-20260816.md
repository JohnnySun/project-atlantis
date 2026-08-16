# M3 story-event E batch 15 round-trip（2026-08-16）

本批次處理遭冷落人物的刺殺延續，以及劉備以民安寧為先的信念被亂世侵蝕的片段
E:026／E:027。完整 source 只在 ignored ROM-derived source table／work；本文件只保存
hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:026、E:027（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077C00`、`0x077C6C` |
| source／target payload | 104／65、72／45 bytes；fixed-slot fit `2/2` |
| source／target lines | 5／5、3／3；target max width `13`／`12` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `2/2`；U+7B49／U+4E82 at indices 15／35 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:026 接續 E:025 的冷遇人物並保留五行刺殺敘事；E:027 保留三行
信念崩解轉折，`等`／`亂` 沿用已通過 bounded source-use gate 的 E-specific slots。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `67e4781e`。
- fixed-slot patch changed `269` bytes；patched ROM SHA-256
  `ff27438637ce0e72b906e051471d423b6e23ceaf70d90e474eb286f7cf848d6d`。
- BPS `342` bytes；BPS CRC32 `472c1774`；BPS SHA-256
  `147b6c6c070e82afe057665dc7f5a34c4e393db73885d7355b7c293157b6bf3d`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `ff27438637ce0e72b906e051471d423b6e23ceaf70d90e474eb286f7cf848d6d`。

## Evidence boundary

E:026／E:027 與遭冷落人物、刺殺及劉備信念轉折的連續片段相符；公開歷史資料只作
術語背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph
cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

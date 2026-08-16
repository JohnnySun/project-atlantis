# M3 story-event E batch 10 round-trip（2026-08-16）

本批次處理夷陵／吳蜀衝突分支的 E:016／E:017。完整 source 只在 ignored ROM-derived
source table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:016、E:017（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077930`、`0x077998` |
| source／target payload | 101／58、101／62 bytes；fixed-slot fit `2/2` |
| source／target lines | 4／4、4／4；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `3/3`；U+570B／U+5433／U+4E82 at indices 23／24／35 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:016／E:017 沿用夷陵／結局流程分類；公開流程只作背景，不能取代
特定 entry 的自然畫面 receipt。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `6b419e2e`。
- fixed-slot patch changed `336` bytes；patched ROM SHA-256
  `2cba927d4c4facc3e82f4721f6927069b5a21f459214448d579c1e05a3cccae5`。
- BPS `412` bytes；BPS CRC32 `9be23232`；BPS SHA-256
  `4713ea311908c74978a3372dac76c1327482e66cbdaeeb0bcf3e2161513623b1`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `2cba927d4c4facc3e82f4721f6927069b5a21f459214448d579c1e05a3cccae5`。

## Evidence boundary

E:016／E:017 與已知夷陵／劉備生死流程分組相符；公開流程只作章節／術語背景，不能
取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph cache→VRAM／tilemap
receipt 與人工 zh-TW 終審仍 pending。

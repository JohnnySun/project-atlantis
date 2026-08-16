# M3 story-event E batch 12 round-trip（2026-08-16）

本批次處理玉璽失去後的漢朝衰退，以及劉備掌權／魏軍片段 E:020／E:021。完整 source
只在 ignored ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型
slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:020、E:021（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077A7C`、`0x077AC8` |
| source／target payload | 72／45、66／47 bytes；fixed-slot fit `2/2` |
| source／target lines | 3／3、3／3；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `1/1`；U+737B at index 34 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:021 保留片段結尾的未完語法，交由 E:022 的後續批次銜接；`魏`
沿用既有 B3EJ codepage，`獻` 使用 E-specific bounded slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `b73ae1c4`。
- fixed-slot patch changed `185` bytes；patched ROM SHA-256
  `403a5e9f620fff53ac4deaa6724564769d4d94945332328d9c306003deae43d5`。
- BPS `247` bytes；BPS CRC32 `2144df1c`；BPS SHA-256
  `f396b91860602039f992c0ae9b8047c0dedece30431c0e3275af85d09f35da2c`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `403a5e9f620fff53ac4deaa6724564769d4d94945332328d9c306003deae43d5`。

## Evidence boundary

E:020／E:021 與漢朝衰退／劉備掌權敘事分組相符；公開歷史資料只作術語背景，不能取代
自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph cache→VRAM／tilemap receipt
與人工 zh-TW 終審仍 pending。

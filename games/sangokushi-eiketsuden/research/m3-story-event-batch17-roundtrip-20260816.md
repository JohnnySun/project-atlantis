# M3 story-event E batch 17 round-trip（2026-08-16）

本批次處理獻帝離開宮廷、劉備失去重建國家，以及漢王朝恢復舊日威勢的結局片段
E:030／E:031。完整 source 只在 ignored ROM-derived source table／work；本文件只保存
hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:030、E:031（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077D8C`、`0x077E0C` |
| source／target payload | 124／92、89／77 bytes；fixed-slot fit `2/2` |
| source／target lines | 5／5、4／4；target max width `12`／`11` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `4/4`；U+737B／U+6B0A／U+570B／U+65BC at indices 34／36／23／28 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

U+6B0A（`權`）的 E-specific slot 是本批次新增的專名字形：read-only
`font_slot_audit.py` 在完整 292-record bounded source-use cohort 中選出 raw `0x8256`／
codepage index `36`，`source_pool_use=false`；licensed Unifont-T plane 仍只保存 hash-only
receipt，沒有提交字型 bytes。這不是 full-ROM raw-unit non-use 或自然畫面 identity 證明。
`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width 或
自然畫面排版。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `62569c89`。
- fixed-slot patch changed `380` bytes；patched ROM SHA-256
  `bce7799bc61eb64cf4438b3222cccc7af2e2aa497d10e8c7fd7f4d042555a098`。
- BPS `480` bytes；BPS CRC32 `0b8ea7ac`；BPS SHA-256
  `3e2648a251b056dc91a6ec93d247290bec776e1f1a311e67f4d0ba1ded5a4f6c`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `bce7799bc61eb64cf4438b3222cccc7af2e2aa497d10e8c7fd7f4d042555a098`。

## Evidence boundary

E:030／E:031 與獻帝離宮、劉備失國及漢王朝復興的連續結局片段相符；公開歷史資料只作
術語背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph
cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

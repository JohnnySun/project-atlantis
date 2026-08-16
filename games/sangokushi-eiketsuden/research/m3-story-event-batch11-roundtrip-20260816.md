# M3 story-event E batch 11 round-trip（2026-08-16）

本批次處理漢朝復興／玉璽敘事的 E:018／E:019 連續 fragment。完整 source 只在
ignored ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型 slot
和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:018、E:019（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077A00`、`0x077A48` |
| source／target payload | 68／45、50／34 bytes；fixed-slot fit `2/2` |
| source／target lines | 3／3、3／3；target max width `13` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；E-specific custom-aware encoder |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `2/2`；U+737B／U+570B at indices 34／23 |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:019 保留 fragment 開頭的 LF；`不過`、ASCII punctuation 和
`即位` 是為既有 B3EJ codepage／固定槽位選出的可逆表達，不新增 glyph slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `30d7082b`。
- fixed-slot patch changed `210` bytes；patched ROM SHA-256
  `86f6faddd2bad0825a8c973fdcd6b18df72f03b41e73c07a7e99a5af50ddd27f`。
- BPS `282` bytes；BPS CRC32 `2144df1c`；BPS SHA-256
  `8ba507ddb3ea0cd53e946ee1a2b3573fdc1551ab803b343770a7ed1547a84ce6`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `86f6faddd2bad0825a8c973fdcd6b18df72f03b41e73c07a7e99a5af50ddd27f`。

## Evidence boundary

E:018／E:019 與漢朝復興／玉璽敘事分組相符；公開人物／歷史資料只作術語背景，不能
取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph cache→VRAM／tilemap
receipt 與人工 zh-TW 終審仍 pending。

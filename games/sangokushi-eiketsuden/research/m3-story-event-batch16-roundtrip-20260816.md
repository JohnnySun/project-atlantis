# M3 story-event E batch 16 round-trip（2026-08-16）

本批次處理宮廷腐敗與劉備衰退的敘事，以及劉備停止重課、力行節約的政策片段
E:028／E:029。完整 source 只在 ignored ROM-derived source table／work；本文件只保存
hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:028、E:029（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x077CB8`、`0x077D2C` |
| source／target payload | 114／70、95／65 bytes；fixed-slot fit `2/2` |
| source／target lines | 5／5、4／4；target max width `13`／`12` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；existing B3EJ codepage，無新增 custom glyph |
| controls | source／target control-byte signatures unchanged；`2/2` |
| E custom plane match | `0/0` |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:028 保留宮廷腐敗、官員肥己與董卓類比；E:029 保留停止重課、
力行節約和禁止宮廷浪費的四行政策轉折。因既有 codepage 可覆蓋，沒有新增 E-specific
custom slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `b8f1a8d2`。
- fixed-slot patch changed `203` bytes；patched ROM SHA-256
  `bc5ac30f1915b2a31ea1df438846212b30e42dbf3718702b43a02464dabe98ea`。
- BPS `242` bytes；BPS CRC32 `997a7b26`；BPS SHA-256
  `469068a4d36efde44fb03cdcee8d8bc2ac28cb000a37216a8927ec68811c5a57`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `bc5ac30f1915b2a31ea1df438846212b30e42dbf3718702b43a02464dabe98ea`。

## Evidence boundary

E:028／E:029 與宮廷腐敗、劉備衰退及政策轉折的連續片段相符；公開歷史資料只作
術語背景，不能取代自然畫面。ledger 維持 `ai_review`；自然 E formatter→glyph
cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

# M3 story-event E batch 7 round-trip（2026-08-16）

本批次處理同一條歷史結局分支的 E:009／E:010。完整 source 只在 ignored
ROM-derived source table／work；本文件只保存 hash、計數、控制碼、固定槽位和 BPS
metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:009、E:010（2 records／2 unique targets） |
| table／record file offsets | E table `0x0CDB64/33`; records `0x07768C`、`0x07770C` |
| source／target payload | 124／81、93／67 bytes；fixed-slot fit `2/2` |
| source line／target line counts | 5／5、4／4；target max width `12` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；既有 B3EJ codepage，無 custom codepoint |
| controls | source／target control-byte signatures unchanged；`2/2` |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 是保守的字符數／行數 budget gate，不宣稱 GBA pixel width
或自然畫面排版。E:009／E:010 沿用 E-specific map 的 bounded source-use audit，
但本批次沒有使用 custom slot。

## Patch／round-trip receipt

- E pointer table SHA-256：`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`。
- B3EJ codepage table SHA-256：`6cf403a4a29e1cfd35c03a7702a96252550b6eec6e7800910227e947f9169924`。
- clean ROM SHA-256：`d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`；patched target CRC32 `20c92a7f`。
- fixed-slot patch changed `215` bytes；patched ROM SHA-256
  `ba894053ccaf6bb2d1c722822174b3bfb6252da2f6d928e44b7b839066bed7ac`。
- BPS `252` bytes；BPS CRC32 `eb43ac96`；BPS SHA-256
  `d56325c661f22197c39fc2a1ea476d6429afea2b01cbc567f18bbb16ca3fb907`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256
  `ba894053ccaf6bb2d1c722822174b3bfb6252da2f6d928e44b7b839066bed7ac`。

## Evidence boundary

E:009／E:010 與 E:003–E:008 同屬本機 hash-only 分組的歷史結局延續，公開 GBA 流程
可支持 `provisional-known-screen-cross`，但尚未在自然畫面看到這兩筆 entry。ledger
維持 `ai_review`；自然 E formatter→glyph cache→VRAM／tilemap receipt 與人工 zh-TW
終審仍 pending。

# M3 story-event E batch 3 round-trip（2026-08-16）

本批次處理 E:003、E:004 兩筆同一條歷史結局分支的四行敘事。完整 source 只在
ignored ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型 slot
和 BPS metadata。

## Static／ledger gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:003、E:004（2 records／2 unique targets） |
| source payload lengths | 101、99 bytes |
| target payload lengths | 70、66 bytes |
| lines／LF | 4 lines each；3 LF each；其它 control bytes 0 |
| bounded layout audit | `audit_story_layout.py` line budget／control invariant／fixed-slot fit `2/2`；最大行數／字符數只作保守 record gate，不是 pixel-width 證明 |
| fixed-slot fit | 2/2 |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | 2/2；標準 raw units 先經 codepage membership 檢查 |
| E custom mapping | U+7B49／U+537B／U+570B → indices 15／16／23；source-use cohort 292 records 中 raw-unit non-use |
| custom glyph plane match | 3/3；Unifont-T primary plane、secondary plane zero-filled |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

E-specific map 是 [`m3-story-custom-glyph-map.json`](m3-story-custom-glyph-map.json)。它
只適用 E:003/E:004，並以 `--include-story` 產生的 292-record ignored source table
作 bounded non-use gate；不宣稱 full-ROM raw-unit non-use。這次也補上 custom patcher 的
target codepage membership gate，避免把缺少 codepage slot 的普通 Shift-JIS unit 誤當成
可顯示字元。

## Patch／round-trip receipt

- `custom_glyph_patch.py --pool story-event` changed `321` bytes；selected re-extract／
  fixed-slot `2/2`；custom glyph plane `3/3`；E 33-entry pointer table unchanged。
- clean ROM CRC32 `a4a1c956`；patched target CRC32 `20bb7ad7`；patched ROM SHA-256
  `8353e8a194aac965dfcd75915c6619ba0feecaa322b7393f96266ee84aedc65d`。
- BPS `406` bytes；BPS CRC32 `768c2f07`；BPS SHA-256
  `0df4a3ee708d67acc64d70298134650113b66f284272dec6127476de8f7ba046`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256 同為
  `8353e8a194aac965dfcd75915c6619ba0feecaa322b7393f96266ee84aedc65d`。

## Evidence boundary

公開攻略與本機 E metadata 已建立結局／分支的 `provisional-known-screen-cross`，並支援
E003/E004 的上下文選批；詳見 [`m3-story-known-screen-cross-20260816.md`](m3-story-known-screen-cross-20260816.md)。
這不是自然畫面截圖，也沒有取得 E 的自然 formatter→cache→VRAM／tilemap receipt。
兩筆 ledger 仍維持 `ai_review`；`孔明`、`劉備`、`趙雲`、`魏` 的字形來自術語表多來源
交叉，須待 B3EJ 結局畫面人工終審。runtime transport negative 仍只表示本次 mGBA
listener 不可用，不表示遊戲自然不可達。

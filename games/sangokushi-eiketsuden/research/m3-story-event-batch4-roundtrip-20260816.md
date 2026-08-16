# M3 story-event E batch 4 round-trip（2026-08-16）

本批次處理同一條歷史結局分支的 E:005。完整 source 只在 ignored ROM-derived source
table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entry | E:005（1 record／1 unique target） |
| source／target payload | 93／66 bytes；fixed-slot fit `1/1` |
| lines／LF | 4 lines；3 LF；其它 control bytes 0；layout／control／fit `1/1` |
| source-free ledger | 1 row；restore→strip byte-identical；source fields 0 |
| target codepage gate | `1/1`；所有輸出雙位元 unit 都在 B3EJ codepage |
| E custom mapping use | U+5433／U+570B／U+537B／U+7B49；292-record bounded source-use non-use |
| custom glyph plane match | `4/4`；indices 24／23／16／15；secondary plane zero-filled |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 只作保守字符數／行數 budget，不宣稱 GBA pixel width 或自然
畫面排版；`吳` 的字形使用 E-specific map，沒有沿用四池與 E source overlap 的既有
raw units。

## Patch／round-trip receipt

- `custom_glyph_patch.py --pool story-event` changed `259` bytes；selected re-extract／
  fixed-slot `1/1`；custom glyph plane `4/4`；E 33-entry pointer table unchanged。
- clean ROM CRC32 `a4a1c956`；patched target CRC32 `1d37a056`；patched ROM SHA-256
  `2547ef9b2c30d05a35cab78af76c28a8432e5cbb0e37a2c1b9fc81d6b5d7b16d`。
- BPS `340` bytes；BPS CRC32 `ba654c13`；BPS SHA-256
  `5341b6775477c36ce7b02599eb5b5d5382c82408b6fbc4f0ebfda8a3b58db4cc`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256 同為
  `2547ef9b2c30d05a35cab78af76c28a8432e5cbb0e37a2c1b9fc81d6b5d7b16d`。

## Evidence boundary

E:005 與 E:003/E:004 同屬本機 hash-only 分組的歷史結局延續，公開 GBA 流程可支持
`provisional-known-screen-cross`，但尚未在自然畫面看到此 entry。ledger 維持
`ai_review`；自然 E formatter→glyph cache→VRAM／tilemap receipt 仍 pending。

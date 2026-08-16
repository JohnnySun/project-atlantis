# M3 story-event E batch 6 round-trip（2026-08-16）

本批次處理同一條歷史結局分支的 E:007／E:008 四行敘事。完整 source 只在 ignored
ROM-derived source table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entries | E:007、E:008（2 records／2 unique targets） |
| record file offsets | `0x0775D0`、`0x077630` |
| source／target payload | 95／66、91／67 bytes；fixed-slot fit `2/2` |
| lines／LF | 4 lines each；3 LF each；其它 control bytes 0；layout／control／fit `2/2` |
| source-free ledger | 2 rows；restore→strip byte-identical；source fields 0 |
| target codepage gate | `2/2`；所有輸出雙位元 unit 都在 B3EJ codepage |
| E custom mapping use | U+95DC／U+7B49／U+5433／U+570B／U+6B64；292-record bounded source-use non-use |
| custom glyph plane match | `5/5`；indices 32／15／24／23／26；secondary plane zero-filled |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot records and existing glyph slots only |

`audit_story_layout.py` 只作保守字符數／行數 budget，不宣稱 GBA pixel width 或自然
畫面排版。`關` 使用新加入的 E-specific index 32；其 raw unit `0x8252` 通過完整
292-record source-use non-use gate，沒有沿用 E source overlap 的既有 raw unit。

## Patch／round-trip receipt

- `custom_glyph_patch.py --pool story-event` changed `408` bytes；selected re-extract／
  fixed-slot `2/2`；custom glyph plane `5/5`；E 33-entry pointer table unchanged。
- clean ROM CRC32 `a4a1c956`；patched target CRC32 `04ffcd87`；patched ROM SHA-256
  `cea14476b02ee25b7a9c81de9260047a07e1901f36873aa90994f64389a376f3`。
- BPS `508` bytes；BPS CRC32 `8945c99b`；BPS SHA-256
  `f9c8890024ac425c04879538c37f896c1ea6adfddde49474915152e185434d30`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256 同為
  `cea14476b02ee25b7a9c81de9260047a07e1901f36873aa90994f64389a376f3`。

## Evidence boundary

E:007／E:008 與 E:003–E:006 同屬本機 hash-only 分組的歷史結局延續，公開 GBA 流程可支持
`provisional-known-screen-cross`，但尚未在自然畫面看到這兩筆 entry。ledger 維持 `ai_review`；
自然 E formatter→glyph cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

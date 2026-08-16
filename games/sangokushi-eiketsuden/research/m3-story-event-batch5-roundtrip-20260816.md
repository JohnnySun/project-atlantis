# M3 story-event E batch 5 round-trip（2026-08-16）

本批次處理同一條歷史結局分支的 E:006 四行敘事。完整 source 只在 ignored ROM-derived
source table／work；本文件只保存 hash、計數、控制碼、字型 slot 和 BPS metadata。

## Static／ledger／layout gate

| 欄位 | 結果 |
|---|---:|
| selected entry | E:006（1 record／1 unique target） |
| source／target payload | 101／54 bytes；fixed-slot fit `1/1` |
| lines／LF | 4 lines；3 LF；其它 control bytes 0；layout／control／fit `1/1` |
| source-free ledger | 1 row；restore→strip byte-identical；source fields 0 |
| target codepage gate | `1/1`；所有輸出雙位元 unit 都在 B3EJ codepage |
| E custom mapping use | U+5433／U+5F9E／U+6B64／U+53EA／U+65BC；292-record bounded source-use non-use |
| custom glyph plane match | `5/5`；indices 24／25／26／27／28；secondary plane zero-filled |
| pointer／codepage tables | unchanged |
| relocation | disabled; fixed-slot record and existing glyph slots only |

`audit_story_layout.py` 只作保守字符數／行數 budget，不宣稱 GBA pixel width 或自然
畫面排版。E-specific map 已由完整 292-record bounded source-use cohort 驗證，沒有沿用
與 E source overlap 的既有四池 raw units。

## Patch／round-trip receipt

- `custom_glyph_patch.py --pool story-event` changed `315` bytes；selected re-extract／
  fixed-slot `1/1`；custom glyph plane `5/5`；E 33-entry pointer table unchanged。
- clean ROM CRC32 `a4a1c956`；patched target CRC32 `f1452014`；patched ROM SHA-256
  `75bc199c2a655172c2545396181c380838731299463384eec32477c68e6a9f9a`。
- BPS `399` bytes；BPS CRC32 `202b0259`；BPS SHA-256
  `62c8b55daeb2a76f980f2f6fb7216a9970b621fd51ca831cdf5279403ed755ea`。
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256 同為
  `75bc199c2a655172c2545396181c380838731299463384eec32477c68e6a9f9`。

## Evidence boundary

E:006 與 E:003–E:005 同屬本機 hash-only 分組的歷史結局延續，公開 GBA 流程可支持
`provisional-known-screen-cross`，但尚未在自然畫面看到此 entry。ledger 維持 `ai_review`；
自然 E formatter→glyph cache→VRAM／tilemap receipt 與人工 zh-TW 終審仍 pending。

# M3 story-event E batch 1 round-trip（2026-08-16）

## Scope

本批次只處理 story-event pool E 的兩筆獨立雙行問題句：E:002、E:011。
原文仍只存在 ignored 本機 source table／work；本文件保存 string ID、hash、偏移、
計數和驗證結果，不保存原文、完整 source table、ROM、patched ROM 或 BPS。

| 欄位 | 結果 |
|---|---:|
| pool table | file `0x0CDB64` / 33 entries |
| selected entries | 002, 011 |
| unique selected targets | 2 |
| source text hash binding | 2/2 restore 成功；ledger 綁定 decoder `source_text_hash` |
| strict codepage coverage | 2/2 |
| target payload fits original span | 2/2 |
| LF/control invariant | 2/2；各保留 1 LF，無其它控制碼 |
| custom raw-unit guard | 17 units loaded；target overlap 0 |
| fixed-slot changed bytes | 94 |
| pointer table | unchanged |
| relocation | disabled |

## Encoder and verifier

`tools/patch_fixed_pool.py` 現在明確接受 `story-event` pool，但 story invocation 必須
提供 `--custom-map research/m3-custom-glyph-map.json`。patcher 會：

1. 以 restored work 的 provenance 驗證 source text／raw source hash；
2. 只用 strict Shift-JIS 與已存在的 1834-entry codepage；
3. 比對 known／unknown format sequence 和所有 `<0x20` control bytes，保留 LF 契約；
4. 拒絕 target 使用四池 custom map 的任何 17 個 raw code units；
5. 只在原始 NUL-terminated record span 內寫入，禁止 table relocation。

這批的 ASCII `?` 是刻意的 safety choice：全形 `？` 會使用 `0x8148`，而該 raw unit
在既有 custom map 與 E source overlap cohort 中，不能直接拿來做 E standard-only
batch。這不是 Unicode identity 推論，也不代表 E 可以使用 custom glyph。

## Round-trip receipt

`verify_fixed_pool_patch.py` 對 clean ROM 與 patched ROM 報告：

- selected re-extract match `2/2`；fixed-slot `2/2`；unselected records byte-identical；
- table E pointer bytes unchanged；所有差異都在 selected record spans；
- source CRC32 `a4a1c956`；patched target CRC32 `210328ca`；
- patched ROM SHA-256 `9e931540ee087c25cbd1623b21a891f438f7c23813547c60cea52b50c598c757`；
- BPS 132 bytes，BPS CRC32 `de6bc4b7`，BPS SHA-256
  `499ce1633001862375528e8c18b7c49440bc54c46b384868ab3912227960e7df`；
- clean ROM + BPS apply 與 patched ROM `cmp` 相同；applied SHA-256 亦為
  `9e931540ee087c25cbd1623b21a891f438f7c23813547c60cea52b50c598c757`。

同一 E pool 的後續 existing-codepage E:032 見
[`research/m3-story-event-batch2-roundtrip-20260816.md`](m3-story-event-batch2-roundtrip-20260816.md)。

## Evidence boundary

本批次證明 E pool 的兩筆 record-level fixed-slot decode→encode→patch→re-extract
與 BPS apply 可逆，且 target 不觸及四池 custom raw-unit guard。尚未證明：

- E 的自然 ending／戰役畫面可達性或自然 event index；
- E writer 後段的自然 formatter→glyph cache→VRAM／tilemap receipt；
- 全 33 筆 E records 的翻譯語意、完整劇情 chain、最大寬度／行數；
- E 使用任何 custom glyph 的安全回插邊界；
- patched ROM 的 mGBA 畫面 QA。

因此 status 仍為 `research`，這個 batch 不代表全遊戲劇情翻譯完成。

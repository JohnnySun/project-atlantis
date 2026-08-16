# M3 劇情事件池 E 靜態邊界與 consumer chain（2026-08-16）

## 結論

在四組既有 bounded pool 之外，ROM 還有一個獨立的劇情／結局事件指標池 E：

```text
file 0x0CDB64 / GBA 0x080CDB64 / 33 entries
    -> static pair helper 0x08011904
    -> writer helper 0x080118C8
    -> text writer 0x0800CAD8
```

這是指標、有效 Thumb 函式邊界、literal pool 和 callsite 的靜態 consumer 證據；
目前仍沒有自然 mGBA runtime hit，因此標記為
`static-consumer-confirmed; known-screen-cross-provisional; natural-runtime-pending`。
本文件只保存 metadata、
offset、計數和 hash，不保存日文原文、record payload、dump 或 glyph 圖片。

## Table E boundary

`tools/analyze_story_pool.py` 對乾淨 ignored ROM 的 bounded 輸出確認：

| 欄位 | 結果 |
|---|---:|
| table file / GBA | `0x0CDB64` / `0x080CDB64` |
| entry count | 33 |
| table end (exclusive) | `0x0CDBE8` |
| preceding word | `0x00030003`（非 ROM pointer） |
| next word | `0x19010502`（非 ROM pointer） |
| following word | `0x02000000` |
| unique target count | 33 |
| target range | `0x077328`–`0x077E68` |
| records containing LF | 32/33 |
| strict Shift-JIS records | 33/33 |
| opaque control bytes | 0 |
| payload length range | 18–124 bytes |

Pointer-table raw bytes 的 SHA-256 為
`729b6f1e24c095811fb7101eb1aea90eca33c1b5d30730338d51361ecf6eb3e9`；依 entry 順序
序列化的 target-offset SHA-256 為
`03f9d9a5492d7781a93c957ec006811f9fe485143bcfb1f9d34da0c15f3ad8f4`。33 個 record
payload 的 ordered source-hash manifest SHA-256 為
`e4136b946043fbf5204528ea4fd0061d2cf30b6f080a0388bb5b3f91598eb30c`；hash 只用於
本機 source drift 檢查，不是原文替代品。

``0x00`` 終止、``0x0A`` 換行和 strict Shift-JIS 可由 bounded analyzer 逐 record
重驗；未知控制 byte 計數為零，不代表完整劇情格式或所有畫面版面已理解。這一池
含有結局／分支敘事型資料，也有跨 record 的換行片段；後續翻譯選批時必須保留
相鄰片段語境，不能只按單一短字串猜測。

## Static consumer evidence

在 `0x0801192C`–`0x08011BE8` 的 Thumb caller span 內，literal slot 共 27 個，
只落在 table E 的 33-entry 範圍；目前已靜態看到 entry 0、1、2、5–15、18–28、
31、32 的引用。未把 caller span 中的其它 branch target 誤標成文字 writer。

可重現的有效 callsites 為：

- caller `0x0801195E`／`0x080119D2` 等呼叫 pair helper `0x08011904`；
- pair helper `0x0801190E`、`0x08011922` 呼叫 writer helper `0x080118C8`；
- writer helper `0x080118D8` 呼叫既有 text writer `0x0800CAD8`。

`0x08011990` 的 literal 為 `0x080CDB64`，而每個已列入的 literal slot 都經過
entry-range、4-byte alignment 和 GBA ROM pointer 檢查。這條鏈與 M2.2 已確認的
writer 後段相接，但尚未取得 E pool 的自然 formatter→glyph cache→VRAM 收據；
因此不能把這個靜態 chain 當成自然可達或 runtime glyph identity 證明。

## Decoder scope and negative boundary

`tools/extract_text_pools.py` 的預設輸出仍然只包含四個既有 bounded pool：

```text
A 0x0CBC54/183, B 0x0D1FFC/44, C 0x0D20D8/4, D 0x0D4D00/28 = 259 records
```

`--include-story` 才會額外輸出本機 ignored 的 292-record source table，且 story
E 的 metadata 與原文資料保持同一個 ignored boundary。這是刻意的 scope gate：
目前 17 個授權 Unifont-T custom mapping 的 source-pool non-use 只對四池 259
records 成立；E pool 的原始 code units 已和現有 mapping 重疊 `0x8141`、`0x8142`、
`0x8148`、`0x8158`。所以不能把既有 custom map 直接套到 E，也不能宣稱全 ROM
custom-glyph non-use。公開攻略對夷陵／劉備生死與結局分支的描述，和 E 的 hash-only
record 分組相符；這只形成 `provisional-known-screen-cross`，不取代自然畫面收據。

## E-specific custom glyph gate

`research/m3-story-custom-glyph-map.json` 是 E:003/E:004/E:005/E:006/E:007/E:008 的獨立 bounded map。它使用
完整 `--include-story` 292-record source table 做 raw-unit non-use audit，選取 codepage
indices `15`、`16`、`23`、`24`、`25`、`26`、`27`、`28`、`32`（U+7B49、U+537B、U+570B、U+5433、
U+5F9E、U+6B64、U+53EA、U+65BC、U+95DC），不使用與 E source
重疊的四個 existing-map units。`custom_glyph_patch.py` 和 `verify_custom_glyph_patch.py`
已對 batch 3／4／5／6 取得 custom plane `3/3`／`4/4`／`5/5`／`5/5`、fixed-slot／re-extract `2/2`／`1/1`／`1/1`／`2/2`、
pointer／codepage table unchanged；這仍不是 full-ROM non-use 或自然 glyph identity 證明。

## Status

| 證據類別 | 狀態 |
|---|---|
| Table E boundary / 33 targets | confirmed |
| NUL / LF / strict Shift-JIS structure | confirmed for bounded pool |
| literal → pair helper → writer static chain | confirmed |
| natural menu／ending reachability | pending; no natural cohort |
| formatter → cache → VRAM receipt for E | unknown / runtime pending |
| E custom-glyph safety | confirmed-static / bounded for E:003–E:008; full-ROM non-use unknown |
| E known-screen／flow cross | provisional-known-screen-cross; see `m3-story-known-screen-cross-20260816.md` |
| E translation ledger | batches 1–6 established for E:002／E:011／E:032／E:003／E:004／E:005／E:006／E:007／E:008; remaining 24 records pending |

下一步只能在 E-specific source-use gate、版面與術語審核之外，再取得自然 formatter→
cache→VRAM／tilemap receipt；若目標需要 `0x8141`／`0x8142`／`0x8148`／`0x8158` 等
custom unit，必須另做 E-specific mapping、source-use audit 和 runtime QA，不得沿用
四池的 custom receipt。

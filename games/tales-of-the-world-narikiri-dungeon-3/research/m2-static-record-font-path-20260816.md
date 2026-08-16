# M2 selected record→codepoint lookup→font asset static path（2026-08-16）

## 範圍

本回合只把既有的 `0x080014F4` format loop、`0x08004D90` codepoint lookup 與
`0x08001414` 32-byte asset arithmetic 套到一筆已確認 strict record
`sjis:0x146EE0`。可重跑工具是
[`tools/static_record_font_path_probe.py`](../tools/static_record_font_path_probe.py)。
工具在本機讀取 record／ROM bytes，但提交輸出只有 code-unit hash、lookup result、
asset index/address、slot hash 與計數；不提交 source text、record raw bytes、glyph
bytes、RAM/VRAM dump 或圖片。

這筆 record 在 strict parser 中是 `4` 個 halfwidth units、沒有 control/newline；
因此 bounded static evaluator 固定使用 format loop 的初始 lookup flag `0`。這不是
runtime register receipt，不能外推到帶控制碼或不同 caller 的 record。

## Confirmed static evaluation

| unit ordinal | lookup table | lookup result | asset index | asset address | slot SHA-256 |
| ---: | --- | --- | --- | --- | --- |
| 0 | `0x080FFF40` (`literal 0x741D84`, index `0x39`) | `0x8C83` | `0x01CC` | `0x080E1644` | `035bc2572f7c11e6c5df4ddb178185fb81f3048fe009360034ab12255c6dfffd` |
| 1 | `0x080FFFBC` (`literal 0x741D88`, special index `0x17`) | `0x7883` | `0x01B8` | `0x080E13C4` | `46271ee12c19a4297fb235e504cb83a5277f443cda1c5b403107abf806176fdc` |
| 2 | `0x080FFF40` (`literal 0x741D84`, index `0x3D`) | `0x0000` | — | — | — |
| 3 | `0x080FFF40` (`literal 0x741D84`, index `0x38`) | `0x8B83` | `0x01CB` | `0x080E1624` | `54c3f20f65a3698a30d6c33397ca4e032746f5532c2332cf25cbe0ba9cdfa34e` |

摘要計數：`4` input units、`4` halfwidth lookup units、`3` nonzero lookup→asset
units、`1` zero-combining/skip、`3` unique asset indices。這固定了本筆 record 的
**static code-unit→lookup-result→asset-slot arithmetic**，並特別保留
`0xDE/0xDF` 鄰接特殊 lookup branch；它不是把半形片假名或 lookup result 當作
zh-TW 翻譯，也不是 glyph 畫面辨識。

## Confirmed / unknown 分層

- **confirmed-static：** exact strict record boundary；`0x08004D90` pointer pool
  slots；halfwidth normal/special table selection；lookup halfword values；nonzero
  result 經固定 double-byte arithmetic 得到的 asset index／address；每個 0x20-byte
  slot 的 hash。
- **unconfirmed：** live source read／caller、runtime lookup flag、private codepage
  completeness、asset slot 的 glyph identity／bpp／width、asset→scratch→VRAM writer、
  control semantics、capacity、pointer rewrite、BPS beyond equal-length POC。
- `0x0000` 的 unit 只記為 lookup zero-combining／skip；不自行命名其遊戲語義。

## 下一個最小切片

在不接管其他 session 的前提下，對已確認 caller／builder 或 `0x08004D90` 設一個
窄 runtime breakpoint，取得同一筆 `r1`／lookup flag／return halfword；接著只對上述
三個 asset slot 中實際命中的一個設 read-watch，向 `0x08001414`／transform scratch
或 writer 追一層。若 listener 仍不可用，這份 static path 只作 provisional
engineering evidence，不得開始翻譯或把 synthetic POC 升格成可發布回插器。

## 重跑

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/static_record_font_path_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --record-offset 0x146EE0 \
  --out /private/tmp/tow-nd3-static-record-font-path.json
```

輸出 JSON 僅是 metadata/hash/count；`/private/tmp` 檔案不得加入 Git。

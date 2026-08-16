# A9PJ M23 font-record static renderer（2026-08-16）

M23 只建立可重跑的 private raster renderer，不宣稱完成 codepage、glyph identity、
control semantics 或 scene classification。輸出的 PGM／PNG 與 OCR 結果都留在
`/private/tmp`；Git 只保留 renderer arithmetic、版本、dimensions、hash 與驗證方式。

## 固定格式與重現

`m23_font_render.py` 讀取：

```text
record_file = 0x89E00 + code_unit * 0x18
record      = 12 little-endian 16-bit rows
bitmap      = 16x12, MSB-first (bit 15 is leftmost pixel)
```

單一 private candidate 的重現命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m23_font_render.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FA616 \
  --output /private/tmp/tow-a9pj-m23-render/candidate-1-msb.pgm \
  --scale 4 --bit-order msb
```

Receipt：`unit_count_including_terminator=20`、`line_advance_candidates=1`、輸出尺寸
`640x96`、PGM SHA-256
`d62ac84e2835dcc73284f65acd472867d759505fe4a76f1dbe469466de9ff00e`。同一串以 LSB-first
產生的 SHA-256 是
`fc389a603054648e0440068d5cf5f2a1914e9fa0ce98965ad5fb916c1a7e9b31`；它把已知鍵盤
假名的左右方向反轉。MSB-first 版本可在已知的 `ユ`、`ニ`、`ト`、`の`、`し`、`ま`、
`す` landmark 上與系統鍵盤 mapping 對齊，故固定為 renderer layout；這只是 raster
orientation proof，不是未知 glyph 的 Unicode identity proof。

`0x0000` 只控制 bounded stream 結束，`0xFF70` 只新增一行；renderer 不把任何
halfword 轉成 Unicode，也不把 PGM／OCR candidate 寫入 source table。所有 target 仍
需 runtime consumer、畫面語境與獨立 codepage 交叉，才可進 ledger。

## 目前證據邊界

- 已證明：24-byte record 的 row geometry、MSB-first static raster、`0xFF70` 的 layout
  line-break candidate，以及 renderer 可在不輸出 source 的情況下產生 private image。
- 未證明：`0xFF70` 的 semantic control name、`0x0001` 是空格或 padding、未知 record
  的 Unicode identity、任何 direct caller 的 plot／map-event／character／battle role。
- 本輪用 `/Applications/Xcode.app` 的 matching Swift toolchain 可編譯並啟動 Vision；
  `VNImageRequestHandler` 對 private glyph image 回報 CVPixelBuffer `-6662`／`nilError`，
  因本機 Vision pixel-buffer environment 未提供 OCR receipt。`xcrun` 的 CommandLineTools
  路徑另有 SDK/compiler mismatch 與 Xcode license gate。這些是工具環境陰性，不是
  codepage negative；人工只確認已知 landmark 的 orientation。後續仍優先以多字串 render
  + 可用的本機 OCR／人工 context alignment，再建立 checksum-qualified local rows。

## 下一個最小缺口

從可用的 fresh A9PJ GDB listener 命中 `0x080063E0`／`0x080063B6`，取得 direct
caller 的 stream pointer、bounded hash、LR 與 screen metadata；再以 direct-caller
候選而不是整個 pointer pool 做全字串 raster／codepage alignment。沒有這個 runtime
context，不開 source row 或 zh-TW ledger。

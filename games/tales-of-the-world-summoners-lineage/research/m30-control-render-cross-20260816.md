# A9PJ M30 `0xFF70` line-advance cross-check（2026-08-16）

M30 將 M20 static parser branch 與 M23 private 16×12 render layout 對照。它只提升
`0xFF70` 的 semantic 到「line advance」；不推導變數、姓名、道具插值或其他 control，
也不輸出 stream bytes、原文或圖片。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m30_control_render_cross_probe.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FA616 \
  --image /private/tmp/tow-a9pj-m23-render/candidate-1-msb.pgm \
  --output /private/tmp/tow-a9pj-m30-control/summary.json
```

## receipt

- stream target `0x1FA616` 在 `0x0000` 前有 1 個 `0xFF70`；bounded renderer output 是
  `640x96`、兩行 layout，PGM SHA-256 為
  `d62ac84e2835dcc73284f65acd472867d759505fe4a76f1dbe469466de9ff00e`。
- parser static evidence 是 compare `0x0800640E`、skip `0x08006410`、horizontal reset
  `0x08006412`、vertical add `0x08006414`（`+0x0C`）與 branch `0x08006416`。
- 因 parser、terminator、private rendered line count 三者一致，M30 receipt 可標
  `line-advance-confirmed-by-parser-and-render-layout`。這不是 direct runtime reader
  breakpoint，也沒有提升其他 units 的 glyph identity。

`0x0000` terminator 已由 parser branch 與 bounded stream 同時支持；`0x0003/0007/0008`
等其他 units 仍依 record／keyboard／context evidence 分開，不能泛稱 control。ledger
gate 仍關閉，因 codepage general mapping、scene coverage 與回插尚未完成。

## 下一個最小缺口

在 name-entry UI candidate 上補一次同一 caller／reader 的 live pointer receipt；並以
至少一個含 `0xFF70` 的 runtime screen hash 交叉 control semantic，再進入最小 source
row schema POC。變數／插值 control 另需獨立 consumer evidence。

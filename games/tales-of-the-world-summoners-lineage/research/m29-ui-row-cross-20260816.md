# A9PJ M29 name-entry UI row cross-check（2026-08-16）

M29 將 M19 clean runtime keyboard gate、BG0 tilemap reconstruction 與 M27 direct static
caller row 做 bounded cross-check。它不是 `0x080063E0` reader breakpoint receipt；工具明確
保留 `reader_breakpoint_hit=false`，但能把一條 row 提升為 screen-and-static-caller
correlated UI candidate。輸出只含 addresses、hash、mapping status 與 gate，不含原文或圖片。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m29_ui_row_cross_probe.py \
  /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl \
  /private/tmp/tow-a9pj-m19-gate-seq-1/summary.json \
  --bg0-image /private/tmp/tow-a9pj-m19-gate-seq-1/bg0-gate.png \
  --output /private/tmp/tow-a9pj-m29-ui/summary.json
```

## evidence

- A9PJ ROM SHA-256：`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- runtime gate：`DISPCNT=0x1B40`、BG0CNT=`0x0001`、BG1CNT=`0x0106`，BG1 keyboard
  screenblock SHA-256 `5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b`，
  selected keyboard positions `8/8`。
- same gate 的 BG0 screenblock SHA-256 是
  `e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661`；以 charbase 0、
  screenbase 0 的 core renderer 重建 private BG0 image，PNG SHA-256 是
  `72d1bf7271453ee012553c152940847c226d82e4470b43009d41963f63410f91`。人工檢視該
  private image 可見 name-entry 的 default-name row 與 `カナ／英数` UI。
- M27 row 的 static caller `0x080526FE`、stream file offset `0x1FA4B4` 與該 name-entry
  function 相鄰；local provisional overlay 對應 `・レスター` candidate，source hash 留在
  private receipt，不把短句寫進 Git。

因此本輪 classification 是 `scene_role_candidate=ui-name-entry`、
`runtime_context_proof=screen-and-static-caller-correlated`；`reader_breakpoint_hit=false`、
confirmed glyph identity 增量 `0`、`eligible_for_ledger=false`。這條 row 的 mapping 仍含
provisional keyboard／punctuation evidence，不能直接建立翻譯 ledger。

## 下一個最小缺口

用可用 fresh listener 對 `0x080526FE` 或 `0x080063E0` 做單一 breakpoint，取得同一
`0x1FA4B4` pointer 的 live register／LR／stream hash；若能補上，才可把這條 UI row 接到
M28 checksum／最小 round-trip POC。劇情、地圖／事件、角色與戰鬥 rows 仍未分類。

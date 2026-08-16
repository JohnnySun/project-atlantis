# A9PJ M27 provisional overlay decoder（2026-08-16）

M27 是 M24 direct static caller decoder 的 local-only variant，額外套入 M25/M26 已分開
記錄的 provisional glyph map：`0x0006/08/09/0A/0C/0D` punctuation，以及 `0x00A8` small
katakana candidate。它不修改 M21 conservative decoder，也不把任何 row 變成 ledger eligible。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m27_provisional_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl
```

JSONL 僅能寫 private／ignored 路徑，因為其中含 local `text`；stdout 只輸出 counts、
mapping status 與 ROM hash。每行固定 `runtime_context=false`、`scene_role=unclassified`、
`eligible_for_ledger=false`，未知 halfword 仍以 `{Uxxxx}` 保留。

## private aggregate receipt

本輪 receipt 為 46 個 direct rows、1 個暫無 unresolved halfword 的 row、63 個 distinct
unresolved units；M27 overlay 只改變候選顯示，不宣稱完整 codepage、control semantic 或
scene role。該 1 row 的 mapping 仍含 provisional statuses，仍需 runtime reader／完整
句子 alignment 與 source checksum 才能進入後續 ledger。

## 下一個最小缺口

用 fresh A9PJ runtime 命中一個 direct caller，將同一 row 的 `stream_sha256`、screen hash、
caller LR 與 output mapping status 對齊；若 listener 仍不可用，先擴充 raster/context
candidate report，但保持 M21/M27 rows local-only。

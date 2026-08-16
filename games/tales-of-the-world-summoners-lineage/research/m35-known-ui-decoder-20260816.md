# A9PJ M35 bounded known-screen decoder（2026-08-16）

M35 把 M32/M34 已通過的兩條 known-screen row 接回既有
`tools/m21_source_decoder.py`，新增的是 `--known-ui-only` 固定模式，不是 broad scan、
provisional overlay 或新的候選層。它只允許兩個 stable ID，並在 clean A9PJ ROM 上重新
讀取固定 offset、terminator、code-unit sequence 與 source hash；source-bearing JSONL
只寫到 `/private/tmp` 或 ignored `research/*-decoded.jsonl`。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --known-ui-only \
  --output /private/tmp/tow-a9pj-m35-known-ui/summoners-lineage-known-ui-decoded.jsonl
```

receipt：

| field | result |
| --- | --- |
| decoder | `m34-known-ui-decoder-20260816.v1` |
| ROM | A9PJ SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`，match |
| known rows considered/emitted | `2/2` |
| terminated rows／complete bounded rows | `2/2`／`2/2` |
| unresolved units／control candidates | `0`／`0` |
| scene roles | `ui-name-entry`、`ui-name-entry-protagonist-name-field` |
| runtime context | `false`；known-screen context `true` |
| general codepage／control semantics | `false`／`false` |
| source text output | local only，`source_text_emitted=true` 僅存在 ignored/private JSONL |

兩列的 source hash 與既有 gate 對齊：

| stable ID | fixed source offset | code-unit count | source hash |
| --- | ---: | ---: | --- |
| `eb94955ec017c9faff85f062` | `0x1FA4B4` | 5 | `4055ab372bbb3feadbf21c328f0eb72e9ceb2874c8979383feb193eb722d4c60` |
| `f4bc65e10318a0204bebc5b0` | `0x087384` | 4 | `8c24214195799be96f68bbd812d4ae8de1a086856c20846cf18c629f1f4283e4` |

M32/M34 的 code-unit→identity mapping 只在各自的 record-raster／BG0 tilemap known-screen
proof 內有效；decoder 輸出 `codepage_status=bounded-known-screen-only`，不會把這 9 個
glyph 變成全 ROM general mapping，也不會把 `0xFF70` 或其他 halfword 自動加入 control
schema。兩列均以 `0x0000` 作為固定終止證據，沒有把一般候選 rows 混入 fixed output。

## 與 ledger 的接線

M35 的兩列可以作為 private source table 重新供給既有 restore／strip 流程；M34 row 的
source-hash round-trip 與 profile-specific BPS receipt 已在
[`research/m34-known-screen-protagonist-name-20260816.md`](m34-known-screen-protagonist-name-20260816.md)
記錄。提交檔仍只保留 `source_hash`，不提交這個 decoder 的 JSONL、ROM、raw dump、圖片
或 work record。

下一個缺口仍是 general Japanese/CJK codepage、control consumer／runtime sequence，以及
劇情、地圖／事件、角色、戰鬥 rows 的 scene classification；M35 不把 bounded eligibility
誤報成完整抽取或翻譯完成。

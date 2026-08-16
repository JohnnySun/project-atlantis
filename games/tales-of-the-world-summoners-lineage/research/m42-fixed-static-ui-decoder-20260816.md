# A9PJ M42 fixed static UI decoder receipt（2026-08-16）

M42 將 M41 的兩列 raster mapping 接回既有 `m21_source_decoder.py`，但採用獨立
`--known-static-ui-only` mode。這不是 broad decoder、provisional overlay 或 ledger
開關：mode 只接受 clean A9PJ hash、兩個固定 stream offset、固定 code-unit sequence、
terminator 與 source hash；所有含 source 的 JSONL 仍在 `/private/tmp`。

## 固定 gate

| check | result |
| --- | --- |
| decoder | `m41-known-static-ui-decoder-20260816.v1` |
| ROM SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`，match |
| fixed rows | `2/2` |
| `0x0000` terminator | `2/2` |
| complete bounded mapping | `2/2` |
| static phrase context | `true` |
| runtime context／non-UI role | `false`／`0` |
| ledger eligible | `false`；existing M32/M34 `2` unchanged |

兩列的 source hash 仍只作 drift receipt；不在 tracked docs 或 translations JSONL 寫入
完整日文 source。M41 的 `0x0003=U+3002`、`0x00A8=U+30C3` 與其他 7 個 mapping
由固定 mode 使用，但沒有因此宣稱 general Japanese/CJK codepage。

## 可重跑命令

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --known-static-ui-only \
  --output /private/tmp/tow-a9pj-m41-static-ui/known-static-ui.jsonl
```

預期 stdout 含 `known_static_rows_considered=2`、`terminated_rows_emitted=2`、
`complete_codepage_rows=2`、`eligible_for_ledger=false` 與 A9PJ hash match。對輸出
做本機 JSONL schema／source-hash 檢查即可確認兩列未漂移；輸出檔不可進 Git。

## 變更與限制

- `STATIC_PHRASE_MAPPING`、`STATIC_UI_ROWS` 與 `decode_known_static_ui_rows()` 位於
  既有 M21 decoder；沒有新增獨立候選掃描器。
- `--known-ui-only` 的 M32/M34 behavior 不變；兩列 M41 rows 不會進入
  `restore_translations.rb` 的 ledger gate。
- game-specific tests 新增固定 mapping／hash gate；整體 tests 仍需配合 shared
  core、ledger codec、translation schema 與 repository safety 一起重跑。

下一個最小缺口仍是同一 codepage 的 non-UI scene 或 live reader／consumer receipt；
M42 不等於完整抽取、翻譯、回插或 runtime QA。

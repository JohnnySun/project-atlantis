# A9PJ M45 fixed static start-menu phrase receipt（2026-08-16）

## 範圍

M45 重用 M21 的 `--known-static-ui-only` fixed mode，將 M37 已人工核對過的
`0x1FA35E` start-menu raster 接回同一個 fail-closed decoder。這不是新的 pointer
掃描器、provisional overlay 或 runtime reader；raw stream、ROM、圖片與含 source
的 JSONL 仍只在 `/private/tmp`。

## 固定證據

| 欄位 | receipt |
| --- | --- |
| ROM | A9PJ SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| source pointer／caller | file `0x1FA35E`／`0x0801A2B0` |
| terminated stream SHA-256 | `14cd36a8e720eab7232e23562bdae105d3c18c4c96e4f836f57d36b25877cf02` |
| M23 raster SHA-256 | `71d91f96745290b383a2beda737c0c7d076e5de55f4b1950e0ec42b3bb9b3d7c` |
| fixed code units | `0x028B,0x0311,0x0073,0x00EF,0x0090,0x009C,0x000C,0x00AE,0x008B,0x00D9,0x008F,0x0000` |
| decoder rows | `3/3` terminated；`3/3` complete within fixed static mapping |

`0x028B` 與 `0x0311` 的 record raster 在既有 M37 bounded phrase context 中分別核對
為 `U+6700` 與 `U+521D`；`0x000C` 在同一 phrase 的長音位置與既有
`0x000C` record／keyboard punctuation evidence 一致，固定為 `U+30FC`。相鄰假名
record 由既有 keyboard table 只作該短句的 raster anchor；不把這些局部 mapping 外推
成 general CJK codepage。

## Decoder gate

```text
decoder = m45-known-static-ui-decoder-20260816.v1
known_static_rows_considered = 3
terminated_rows_emitted = 3
complete_codepage_rows = 3
static_phrase_context_confirmed = true
runtime_context_confirmed = false
non_ui_scene_confirmed = false
eligible_for_ledger = false
general_codepage_confirmed = false
control_code_semantics_confirmed = false
```

可重跑命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --known-static-ui-only \
  --output /private/tmp/tow-a9pj-m45-static-ui/known-static-ui.jsonl
```

輸出檔含日文 source，只能留在 ignored/private 路徑。tracked decoder 只保存固定
offset、unit、hash、mapping status 與 fail-closed checks；不含 raw glyph bytes。

## 邊界與下一個缺口

M45 將 fixed static source coverage 從兩列擴成三列，並獨立確認兩個 bounded 漢字與
一個長音 glyph；沒有新增 candidate 數，也沒有增加 ledger row。它仍不能替代
non-UI（地圖／事件、角色或戰鬥）scene、live reader／consumer、control schema 或
patched runtime QA。下一步應在既有 M32/M34 bounded target plumbing 上取得可審核的
zh-TW glyph／font policy，或取得一個獨立 non-UI static row；不要把 M45 fixed mapping
當成完整日文碼頁。

# A9PJ M21 private Japanese candidate decoder（2026-08-16）

這個切片首次建立可重跑的本機 `research/*-decoded.jsonl` 產物，但**不是**可提交
source table，也不是翻譯開始。ROM、日文 `text` 與 JSONL 只留在 `/private/tmp`；Git
只保留 decoder、schema 說明與 aggregate receipt。

## decoder contract

`tools/m21_source_decoder.py` 以 clean A9PJ ROM 為唯一遊戲輸入：

1. 重用 `m20_text_record_probe.py` 的 4-byte ROM pointer scan、`0x0000` bounded
   terminator 與 stable candidate ID。
2. 從 clean ROM `0x0808884C` 的 65-entry name-entry rows 產生假名候選；row 0
   前五個（`あいうえお`）沿用 M20 的 table/runtime proof，其餘 keyboard-order labels
   明確標為 provisional。
3. `0xFF70` 只寫成 `{FF70}` control candidate；未解析 halfword 寫成 `{Uxxxx}`，不
   猜 Unicode、控制碼 semantic 或 scene role。
4. 每行都帶 A9PJ SHA-256、pointer／target file offset、terminator、decoder version、
   normalized `source_text_sha256`、mapping status、unresolved-unit metadata，並固定 `runtime_context=false`、
   `scene_role=unclassified`、`eligible_for_ledger=false`。

因此這個工具是「可重跑的候選日文 source 產生器」，不是已完成的完整 codepage decoder。
`source.text` 只會寫入被 `.gitignore` 排除的 local JSONL，工具 stdout 只有摘要。

## private receipt

重跑命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m21-decoder/summoners-lineage-decoded.jsonl
```

本機 receipt（`m21-source-decoder-20260816.v1`）：

| 欄位 | 值 |
| --- | ---: |
| A9PJ SHA-256 match | true |
| pointer references considered | 8,066 |
| terminated rows emitted locally | 7,553 |
| rows with only currently mapped keyboard candidates | 771 |
| partial／unresolved rows | 6,782 |
| distinct unresolved code units | 32,426 |
| runtime context confirmed | false |
| scene roles confirmed | false |
| eligible for ledger | false |

「771 rows」只表示沒有留下 `{Uxxxx}` 或 `{FF70}` 的 bounded candidate，不表示它們已
是劇情文字、已完成通用 codepage，或可以翻譯；因為 caller／畫面語境仍未分類，所有
rows 仍不可進 `translations/`。

## source／ledger gate

這個本機 JSONL 可作為未來 `restore_translations.rb` 的 source-table 輸入，但目前沒有
任何 committed ledger row。下一個必要證據是：以 runtime reader／caller 與 screen context
把候選分成 UI、事件、角色／戰鬥等，再補齊 kanji、special glyph、變數與 control
semantic；完成後才可對少量穩定 row 做 source hash／round-trip POC。

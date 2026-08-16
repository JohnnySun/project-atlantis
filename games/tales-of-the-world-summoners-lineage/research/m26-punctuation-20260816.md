# A9PJ M26 keyboard punctuation candidate audit（2026-08-16）

M26 把 M19 private keyboard page 右側固定 punctuation cluster 與 clean-ROM table／font
record 對照，並以 M24 direct static callers 做 bounded occurrence count。它不把 punctuation
當控制碼，也不增加 confirmed glyph identity；輸出只有 table position、record hash／ink
count、target／occurrence count，沒有 stream、原文、圖片或 OCR。

## candidates

| code unit | keyboard layout candidate | status |
| ---: | --- | --- |
| `0x0006` | `・` | keyboard-layout-provisional |
| `0x0008` | `?` | keyboard-layout-provisional |
| `0x0009` | `!` | keyboard-layout-provisional |
| `0x000A` | `＿` | keyboard-layout-provisional |
| `0x000C` | `ー` | keyboard-layout-provisional／另見 M25 context evidence |
| `0x000D` | `/` | keyboard-layout-provisional |

M19 的 visible hiragana page 將這些符號放在固定 screen positions；clean-ROM row 0
table 的 arithmetic 對應 selection 59–64。這足以建立 layout candidate，但沒有
font-record→BG1 byte-identical transfer receipt，故不提升為 confirmed general codepage。

## 重現與 private receipt

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m26_punctuation_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m26-punctuation/summary.json
```

版本為 `m26-punctuation-probe-20260816.v1`，輸入 SHA-256 應為
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。M26 receipt 會保留
六個 candidate 的 record／table／direct-caller metadata，並將 confirmed increment、
control semantic、runtime scene 與 ledger eligibility 固定為 false。

## 下一個最小缺口

對一個 punctuation slot 或 direct caller 取得 fresh runtime read／screen evidence，
並把 keyboard layout candidate 與 actual renderer glyph 做 byte／hash cross-check；在此
之前，M21 decoder 仍以 `{Uxxxx}` 保存這些 units，不能開始翻譯。

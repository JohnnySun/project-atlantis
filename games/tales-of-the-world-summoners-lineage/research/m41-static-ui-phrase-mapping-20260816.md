# A9PJ M41 static UI phrase／glyph mapping boundary（2026-08-16）

M41 沿用既有 M24/M27 的 46 筆 direct rows 與 M23 renderer，只挑兩條已存在的
ROM-literal stream 做重複 raster reading；沒有掃描新 pointer、建立 overlay 或寫入
source table。PGM、ROM 與完整原文均留在 `/private/tmp`。本輪目的是取得一小組可
獨立重算的日文／CJK glyph mapping，並把真正的 glyph code unit 與 `0x0000`／
`0xFF70` 控制候選分開。

## 固定 rows 與交叉證據

| row | caller | stream file offset | stream SHA-256 | raster SHA-256 |
| --- | --- | --- | --- | --- |
| attack-unit prompt | `0x080509CC` | `0x1FAA24` | `e9cdfcfc…acde29` | `057f9cb0…cc23` |
| class-selection prompt | `0x0805835A` | `0x1FA1DC` | `e61d357f…13b6f` | `3a643a6e…f54` |

兩列都由既有 `0x080063E0` null-terminated consumer 消費，且每列都有 `0x0000`
terminator。M23 以既有 MSB-first、16×12、record stride `0x18` raster；第一列
的語意是「選擇要攻擊的單位」提示，第二列是「選擇職業」提示。兩列的共同片段
逐 glyph 對齊，並非依單一未知 glyph 外形或英文 patch 猜測。

## bounded code-unit mapping

下列 mapping 只在兩列的 static phrase context 中標為 `static-phrase-confirmed`；它
不是 general runtime codepage，也沒有把 record bytes 或 source text 放入提交檔。

| code unit | Unicode identity | static occurrence |
| ---: | --- | --- |
| `0x04F4` | `U+653B` 攻 | attack-unit prompt 首字 |
| `0x058F` | `U+6483` 撃 | attack-unit prompt 次字 |
| `0x00A8` | `U+30C3` ッ | attack-unit prompt 的「ユニット」片段；亦與 keyboard slot candidate 相符 |
| `0x00FB` | `U+3092` を | 兩列共同片段 |
| `0x03A8` | `U+9078` 選 | 兩列共同片段 |
| `0x00FD` | `U+3093` ん | 兩列共同片段 |
| `0x00AB` | `U+3067` で | 兩列共同片段 |
| `0x009D` | `U+3060` だ | 兩列共同片段 |
| `0x0003` | `U+3002` 。 | 兩列句尾 glyph；不是 control branch |

其中 `0x0003` 仍然是 nonzero unit，沿 M37 已確認的 dispatch 進入
`0x080049A0 + unit*0x18` font-record consumer；它在兩個獨立句尾 raster 中呈現同一
日文句點，故本輪將它從「未命名 control candidate」降為
`static-glyph-punctuation`。這不影響 `0x0000=terminator` 或 `0xFF70=line-advance`
的既有分欄。

每個 mapping 的 24-byte record hash 可由 clean A9PJ 以
`0x08089E00 + unit*0x18` 重新計算；不同 code unit 不因語意相近而靜默合併 record。
M41 只保存上述 code-unit／Unicode／row-role metadata，沒有建立可提交的完整日文
source table 或翻譯 row。

## scene／ledger 邊界

兩個 caller 的 static arguments、重複句列與 raster 只足以把 rows 分類為
`ui-selection-prompt-static`；沒有 fresh runtime reader、screen state、VRAM store
stop 或非 UI scene。故：

| gate | result |
| --- | --- |
| bounded Japanese/CJK glyph identities | `9` static phrase mappings |
| `0x0000` terminator | confirmed by both streams |
| `0xFF70` line advance | remains separate candidate；本兩列未使用 |
| `0x0003` control | rejected for these rows；static glyph punctuation |
| non-UI scene role | `0` |
| new ledger-eligible rows | `0`；M32/M34 existing `2` unchanged |

因此 M41 打開的是有限的 mapping／control evidence，不是一般 codepage 或劇情／事件
翻譯 gate。下一步仍需沿既有 rows 取得獨立 non-UI（地圖／事件、角色或戰鬥資料）
語境，或取得 live reader／consumer receipt，才可把 mapping 接入更大 source table。

## 可重跑命令

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m23_font_render.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FAA24 \
  --output /private/tmp/tow-a9pj-m41-row28.pgm --scale 8

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m23_font_render.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FA1DC \
  --output /private/tmp/tow-a9pj-m41-row30.pgm --scale 4
```

預期為 `terminated_by_0000=true`、`line_advance_candidates=0`；只需對輸出 PGM
計算 SHA-256，即可重建本文件的 raster receipt。輸出位置必須保持 private／ignored。

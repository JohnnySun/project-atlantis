# A9PJ M33 Latin target encoder／relocation POC（2026-08-16）

M33 沿用 M32 唯一已 eligible 的 `ui-name-entry` row，只處理一個 bounded target
subset：保留該 row 的既有中點 code unit，並以 name-entry keyboard 的 Latin row
編碼拉丁字母。這不是一般日文 codepage、CJK encoder 或全 ROM 回插器；輸出 ROM、
BPS、raw bytes 與工作表都留在 `/private/tmp`。

## Static Latin table proof

clean A9PJ ROM SHA-256 仍為
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。既有 keyboard
table base 為 `0x0808884C`，row 2 的 52 entries 位於 file
`0x88950`–`0x889D2`（end-exclusive）。entry／font record 關係仍是 little-endian
halfword 與 `0x08089E00 + code_unit*0x18`。

row 2 的 keyboard selection order 與 record raster 交叉結果如下：

| selection range | visible-order identity | code-unit arithmetic |
| --- | --- | --- |
| `0..24` | `A`–`Y` | `0x002A + 2*i` |
| `25..49` | `a`–`y` | `0x002B + 2*(i-25)` |
| `50` | `Z` | `0x005C` |
| `51` | `z` | `0x005D` |

52 個 code unit 全部 distinct，52/52 record 非空。以既有
`m23-font-render-20260816.v1` 的 16×12、MSB-first renderer 將 row-2 record 按
keyboard order 排列，private PGM 為 1344×108、SHA-256
`3341e1569493d90f897bba9d84e258958356eeee786d70950ea5e41e5fb4ec97`；人工檢查只
確認固定 Latin glyph order，不使用 OCR，也不把這張圖片放入 Git。這提升的是 bounded
static Latin identity；沒有 runtime row-2 tilemap receipt，因此不提升一般 codepage。

可重跑 probe（stdout／JSON 只含 metadata；target 是目標而非日文 source）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m20_keyboard_codepage_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --row 2 --count 52 \
  --target-text '・Lester' \
  --output /private/tmp/tow-a9pj-m33-static/row2-target.json
```

bounded encoder receipt：target 編碼 bytes 14 bytes、SHA-256
`8f9a9fea22c4144241440bb2bf151b932b2debc688285054ba65b3406c93cfe0`；加上
`0x0000` terminator 後 stream 為 16 bytes、SHA-256
`d1aaebd056ea200ea04c7271763e8f135103e11fac128ff3fab76f74de7e308d`。中點的
`0x0006` 是 M32 row 的 preserved unit，不宣稱已解開整體 punctuation codepage。

## Actual bounded reinsertion

`m33_target_reinsertion_poc.py` 只接受預期的 M32 caller literal，並採用明確的
append relocation policy：

```text
caller literal file 0x52720:
  old bus 0x081FA4B4 -> new bus 0x08800000
relocated stream:
  file 0x800000, 16 bytes, terminated by 0x0000
```

重跑：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m33_target_reinsertion_poc.py \
  /private/tmp/project-atlantis-a9pj.gba --target-text '・Lester' \
  --output /private/tmp/tow-a9pj-m33-reinsert/target.gba \
  --receipt /private/tmp/tow-a9pj-m33-reinsert/receipt.json

ruby core/patches/bps_create.rb \
  /private/tmp/project-atlantis-a9pj.gba \
  /private/tmp/tow-a9pj-m33-reinsert/target.gba \
  /private/tmp/tow-a9pj-m33-reinsert/m33-latin-relocation.bps
ruby core/patches/bps_apply.rb \
  /private/tmp/project-atlantis-a9pj.gba \
  /private/tmp/tow-a9pj-m33-reinsert/m33-latin-relocation.bps \
  /private/tmp/tow-a9pj-m33-reinsert/applied.gba
cmp /private/tmp/tow-a9pj-m33-reinsert/target.gba \
  /private/tmp/tow-a9pj-m33-reinsert/applied.gba
```

private receipt：target image 8,388,624 bytes、SHA-256
`1b4ce53cfd2026532d02ca3d2a8e9fb72ec7b5fb7600c69e0c17da6d23a7f9c7`；BPS 53 bytes、
SHA-256 `4a6078ca3fffbb6b48c2e81f477b22f1f6d373d7c84474435e37ed6bd20f130d`。
`bps_apply.rb` 的 output 與 target image byte-identical。原始 8 MiB image 只改動
caller literal 的 3 個 bytes，原 `0x1FA4B4` stream bytes 保持不變。

## Re-extract receipt and boundary

POC 重新從 patched image 讀取新 pointer，得到 8 個 halfword（含 terminator），7 個
target units 全部落在 bounded encoder，unresolved count `0`；重新組出的 target bytes
SHA-256 仍為 `8f9a9fea22c4144241440bb2bf151b932b2debc688285054ba65b3406c93cfe0`。
這是 target stream 的 re-extract／BPS round-trip，不是 clean Japanese source hash
不漂移證明；clean source stream 仍留在原位置且未修改。

M33 的明確判定：

| gate | result |
| --- | --- |
| static row-2 Latin table／record arithmetic | bounded pass |
| target encoder | Latin letters + preserved `0x0006` only |
| actual byte-changing relocation | pass, one M32 caller literal |
| BPS create/apply equality | pass |
| CJK／general Japanese codepage | not confirmed |
| variable／name／item controls | not confirmed |
| mGBA runtime QA of patched image | not confirmed |

本輪 fresh headless mGBA 嘗試的 GDB stub 回報 `Debugger: Couldn't open socket`，因此
沒有把 static／BPS receipt 冒充 runtime screen proof；自己啟動的 process 已停止，其他
session listener 未觸碰。下一個最小缺口是取得至少一個非 Latin、最好是可由日文／漢字
font table 與獨立畫面語境交叉的 code-unit identity，並再評估 text width／relocation
policy；在此之前不擴大 M33 encoder，也不批次翻譯。

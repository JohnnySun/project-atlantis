# A9PJ M20 M1.7 glyph／BG0 screen metadata cross-check（2026-08-16）

這是一個只保留 metadata 的交叉檢查，不是新的原文抽取或翻譯切片。它把 M1.7
font-record renderer 在 store 後立即讀到的 32-byte tile hash，和同一份 private core
capture 後段的 VRAM／BG0 tilemap metadata 對齊；不把 tile bytes、圖片或 source text
寫入 Git。

## 輸入與界線

| 欄位 | 值 |
| --- | --- |
| ROM | A9PJ／TOW SUMMLINE／8 MiB |
| ROM SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| M1.7 summary | `/private/tmp/tow-a9pj-m17-runtime-final/summary.json` |
| final VRAM | `/private/tmp/tow-a9pj-m17-runtime-final/vram.bin` |
| private output | `/private/tmp/tow-a9pj-m20-glyph-cross/summary.json` |
| renderer layer | BG0；`BG0CNT=0x0001`，charbase `0x0000`，screenbase `0x0000` |
| tool | `m20_glyph_screen_cross_probe.py`，`m20-glyph-screen-cross-probe-20260816.v1` |

M1.7 的 input path 是 keyboard gate 通過後的 `A` → `0x005E`、`RIGHT` → 第二格、
`A` → `0x0066`。BG1 keyboard gate 仍是 `8/8`；這裡的鍵盤名稱只作為系統排列／輸入
位置證據，不能用孤立外形取代 byte-level transfer receipt。

## BG0 tilemap 對齊

兩個 code unit 的 renderer store 目的位址、tile ID 和 final BG0 screenblock 位置均能
對齊。`entry` 的 flip／palette metadata 也保留在 private JSON；下面只列核對所需的
位址與 hash。

| code unit／鍵盤位置 | store destination | tile ID | BG0 `(x,y)` | immediate post-store hash | final VRAM hash | 是否相同 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `0x005E`／`a-row-1`／あ | `0x060020E0` | `0x107` | `(14,4)` | `e4e4d7a2c175ff1948a21042c922cddeb99f8b003060ec9e8d21e99c7d0de26b` | `a9564920d553b7ad2a8b2562e3c02b231992ca28e8b4dece84e65deddb626e29` | no |
| `0x005E`／`a-row-1`／あ | `0x06002320` | `0x119` | `(14,5)` | `4f7234b450f09d6c001ed82c962bc5ffd5633ce43eb7013208fe196fe88e3e6c` | `5f0a3f740aa36e1f6313bbee99ed04e8a0b631ca105b683d83b65f4f9218f2b2` | no |
| `0x0066`／`a-row-3`／う | `0x06002100` | `0x108` | `(15,4)` | `316efab5906d81656c22df3b35e82fc7fc6f1022b345ac5288434d0453450b96` | `8f89099c2a087dd6a4c3e64bacf2d7c86a58eb22ee091e578730cfec6d06f52f` | no |
| `0x0066`／`a-row-3`／う | `0x06002340` | `0x11A` | `(15,5)` | `136fb23c046f15a3a312ff8f1f693b88c5be609558e216c86852a306b0914ef0` | `136fb23c046f15a3a312ff8f1f693b88c5be609558e216c86852a306b0914ef0` | yes |

把兩個垂直 tile 的 4bpp ink mask 合成 8×16 metadata，可得到：

| code unit | ink pixel count | combined ink-mask SHA-256 |
| ---: | ---: | --- |
| `0x005E` | 34 | `467c29391a48516712104b1684f1f73c8dd0ed9ea1d2e45c4300f6996b0587a1` |
| `0x0066` | 11 | `d41af317e7edff1a22e884abdd9345a9912d9cea1d79a61a77dc19693a963cd8` |

這支持「目的 tile 已被 BG0 screenblock 使用」的幾何關係，也重現了 private rendered
grid 的形狀摘要；但 final dump 不是 store stop 的同一時刻，前三筆 tile 的 final hash
已不同。因此不能把 final screen bytes 宣稱為該次 store 的 byte-identical 結果。

## 因果鏈判定

| 維度 | 判定 |
| --- | --- |
| table arithmetic | confirmed：`0x08089E00 + unit*0x18`，record hash／read receipt 已有 |
| runtime consumer | confirmed：`0x08004C82`／`0x08004D1A`，writer class `cpu-game-rom`，M1.7 store receipt 已有 |
| keyboard position | confirmed as bounded input path：BG1 `8/8` gate、第一／第二排列位置；不是 tile byte equality |
| BG0 tilemap geometry | confirmed：四個 destination tile ID 與 `(14,4)/(14,5)/(15,4)/(15,5)` 對齊 |
| same-time tile bytes | **not confirmed**：immediate post-store 與 final VRAM hash 有三筆不一致 |
| DMA／BIOS copy | not observed；本鏈是 CPU renderer store，不能填補 source-copy receipt |
| glyph identity | `0 confirmed / 2 provisional`，identity gate 保持關閉 |

本次的精確 negative 是：**final VRAM dump 的 tile hash 不足以證明該次 CPU store 就是
目前 screenblock 所顯示的 bytes**。因此不建立 source row、codepage mapping、控制碼
語意或翻譯 ledger。下一個最小 runtime 缺口是在同一個 store breakpoint 停止時，同步
讀取 BG0 screen entry 與目的 tile hash；若仍有後續 renderer 覆寫，再追一次上游 caller
或以 store stop 的 metadata 作為唯一 receipt。

## 重跑

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m20_glyph_screen_cross_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  /private/tmp/tow-a9pj-m17-runtime-final/summary.json \
  /private/tmp/tow-a9pj-m17-runtime-final/vram.bin \
  --output /private/tmp/tow-a9pj-m20-glyph-cross/summary.json
```

輸出只含 record／tile／screen metadata、hash、counts 和判定；raw VRAM、ROM、圖片及
完整原文仍留在 private／ignored 路徑。

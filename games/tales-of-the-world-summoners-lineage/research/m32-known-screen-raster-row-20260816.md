# A9PJ M32 known-screen record raster row（2026-08-16）

M32 是在 M29 既有 `0x080526FE → 0x1FA4B4` UI candidate 上做的單一、固定範圍
known-screen cross。它沒有新增 provisional overlay、frequency scan 或 checksum
candidate；只把同一個已捕捉畫面的 ROM record、最終 BG0 raster 與 BG0 tilemap
metadata 放在一個可重跑 gate 中。所有 ROM、VRAM、圖片、PGM 與含 source 的 local
JSONL 都留在 `/private/tmp`，本文件只保存 hash、位址、座標與計數。

## 輸入與重現

私有輸入：

- clean A9PJ ROM：`/private/tmp/project-atlantis-a9pj.gba`，SHA-256
  `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- M19 runtime gate：`/private/tmp/tow-a9pj-m19-gate-seq-1/summary.json`，SHA-256
  `c2a606b84644ce04c8d0059a191b3d6e0b92c3801ce72b5a14cdec6a38f2b708`。
- M19 BG0 reconstruction：`bg0-gate.png`，256×256 RGB，SHA-256
  `72d1bf7271453ee012553c152940847c226d82e4470b43009d41963f63410f91`。
- M19 VRAM dump：`dump/vram.bin`，SHA-256
  `6662c7de25340739f352e19f8634dbcd8b2318892481b2599ea1e9b927924da1`。
- M17 runtime summary：`/private/tmp/tow-a9pj-m17-runtime-final/summary.json`，SHA-256
  `16ee986573bbf29710b6a0cc1f76933677149969ca08bbd72fd6d96adeeef66a`。
- M23-compatible private static render of the bounded stream：80×12 MSB PGM，SHA-256
  `167212a94aef2c9e740b0b77239a774c1b3d9dc85fc9c9065d504b87958a07e0`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m29_ui_row_cross_probe.py \
  /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl \
  /private/tmp/tow-a9pj-m19-gate-seq-1/summary.json \
  --rom /private/tmp/project-atlantis-a9pj.gba \
  --bg0-vram /private/tmp/tow-a9pj-m19-gate-seq-1/dump/vram.bin \
  --bg0-image /private/tmp/tow-a9pj-m19-gate-seq-1/bg0-gate.png \
  --m17-summary /private/tmp/tow-a9pj-m17-runtime-final/summary.json \
  --output /private/tmp/tow-a9pj-m32-known-screen/summary.json
```

輸出 `source_text_emitted=false`。M32 使用 M29 同一個 private local JSONL 作為
candidate input；不把該檔案或 output 移入 `research/` 或 Git。

## 固定 row 與 record arithmetic

candidate metadata：

| 欄位 | 值 |
| --- | --- |
| `string_id` | `eb94955ec017c9faff85f062` |
| caller | `0x080526FE` |
| stream file offset | `0x1FA4B4` |
| bounded stream units | 5 |
| terminator | `0x0000` |
| stream bytes SHA-256 | `ba5fcf40ea248f9662571951de19c7447854d76f069091ed5b6f845d2b149d88` |
| local source hash | `4055ab372bbb3feadbf21c328f0eb72e9ceb2874c8979383feb193eb722d4c60` |
| in-row `0xFF70` / other control candidate | `0` / `0` |

使用已證實的 `record_bus = 0x08089E00 + code_unit*0x18`。五個 unit 的 record
hash 與 16×12 MSB-first ink-mask hash 如下；不保存 glyph bytes 或原文：

| code unit | record bus | record SHA-256 | screen bbox（左、上、右、下；右下不含） | mask SHA-256 |
| --- | --- | --- | --- | --- |
| `0x0006` | `0x08089E90` | `859f3e53f64e83939b8cc8aa8662bc6ac4c83c177875f5762a66f1cce752534d` | `(149,37,151,39)` | `27ecd0a598e76f8a2fd264d427df0a119903e8eae384e478902541756f089dd1` |
| `0x00F6` | `0x0808B510` | `11ed35e98e5a20b31a870c1f02c4277aa2c54243c3a3d93636483c1edf8e4b93` | `(158,33,166,43)` | `a6228b8b625dad1d6c55e0b569c5c0a5be759b9f23c0e0dd8820ca4ecb9720d4` |
| `0x0090` | `0x0808AB80` | `bf5efd2a4d79d8de5dfde3eb7f5bb9a59196ef94c1cce7d500851907b6eabdea` | `(169,33,179,43)` | `b662beb8b72eac94eb157916cb50c8c295a9a0e8176a739b9d4b4c2527e9d8aa` |
| `0x009C` | `0x0808ACA0` | `78ac4d2f9cef751746e91d6da6595051ab5d5a27ba7e582a049ceaa47ba096e4` | `(181,32,190,43)` | `657d500d4942c8cc6eac09e84b96f16990529f5456a98b1588373bc8cc109053` |
| `0x000C` | `0x08089F20` | `37618669f3f6cba37d72a987f95d14d1f2b645159b6c8962482df69f887f5e83` | `(192,36,203,38)` | `26255bd84df17449d01b78d69a863dbd9c6d74ae381df7374c6f2986d27e5c25` |

每一列的 ROM record mask 與同一 BG0 final image 的對應 component mask 都是
byte-for-byte equal：`5/5`。這是已知畫面內容、record arithmetic 與 raster 的
三方交叉，不是孤立 glyph 外形或 OCR 判讀。

## BG0 tilemap／runtime gate 交叉

M19/M17 同一畫面：`DISPCNT=0x1B40`、BG0CNT=`0x0001`、BG1CNT=`0x0106`；BG1
screenblock SHA-256 為
`5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b`，鍵盤固定位置
為 `8/8`。BG0 screenblock SHA-256 為
`e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661`。

五個 row 元件各對應 BG0 screenbase `0x0000` 的上下兩格；tile entry、tile ID 與
final 32-byte tile hash 全部 `10/10` 相符：

| code unit | top `(x,y)/tile` | bottom `(x,y)/tile` | raw final hash note |
| --- | --- | --- | --- |
| `0x0006` | `(18,4)/0x10B` | `(18,5)/0x11D` | exact；bottom 是 blank hash |
| `0x00F6` | `(19,4)/0x10C` | `(19,5)/0x11E` | exact |
| `0x0090` | `(21,4)/0x10E` | `(21,5)/0x120` | exact |
| `0x009C` | `(22,4)/0x10F` | `(22,5)/0x121` | exact |
| `0x000C` | `(24,4)/0x111` | `(24,5)/0x123` | exact；bottom 是 blank hash |

這裡的 raw tile hash 是最終畫面 tile receipt，不表示 ROM record bytes 直接搬到
VRAM；record→final tile 的像素表示是經過 renderer transform 的。另行對 M17 的
bounded CPU-store／final-tile audit 得到 `2/12` raw hash equality，且兩筆都只是
`SHA256(32 zero bytes)=66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925`。
因此 `raw_byte_copy_confirmed=false`，不能把這個 negative 改寫成 CPU／DMA source
receipt。

## Gate 判定與分離邊界

M29 v2 的 gate checks：

| check | 結果 |
| --- | --- |
| A9PJ ROM SHA-256 | pass |
| bounded stream／`0x0000` terminator | pass |
| record hash | `5/5` pass |
| record mask→final BG0 image mask | `5/5` pass |
| BG0 tilemap entry／tile hash | `10/10` pass |
| BG1 keyboard gate | `8/8` pass |
| reader breakpoint | 未命中 |
| CPU/DMA/BIOS byte-identical copy | 未確認 |
| general codepage | 未確認 |
| general control schema | 未確認；本 row 無 in-row control candidate |

所以本 row 的 classification 是：

```text
scene_role = ui-name-entry
runtime_context_proof = known-screen-record-raster-and-tilemap-correlated
glyph_identity_confirmed_by_this_probe = 5
reader_breakpoint_hit = false
raw_byte_copy_confirmed = false
eligible_for_ledger = true（只限這一條已知畫面 row）
```

這不表示 7,553 個候選 row 已解碼，也不把 `0x005E`／`0x0066` 的 M1.7 BG0 CPU
renderer 與 BG1 keyboard asset 合併。M1.7 的 caller/LR、目的 charblock 與 M32 的
BG0 final tilemap 仍是 independent renderer evidence；共同 codepage、事件／地圖／
角色／戰鬥語境與 live reader 仍待後續切片。

## 專有名詞來源邊界

本 row 的畫面語境是固定人名欄位，但本文件不保存日文 source fragment。日文正式
角色頁與發布資料採用同一拉丁姓氏拼寫；[Bandai Namco 官方角色頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/chr/index.html)
列出角色頁，[Game Watch 發表資料](https://game.watch.impress.co.jp/docs/20030109/samo.htm)
也使用相同姓氏，[Bandai Namco 發布 PDF](https://www.bandainamcoent.co.jp/corporate/press/namco/48/48-046.pdf)
再次確認主角與先祖的姓氏關係。搜尋 `zh.wikipedia.org/zh-tw` 與巴哈姆特未找到
可直接核對本作角色的條目；臺灣舊攻略索引只足以核對遊戲異名，不能單獨定案人名
音譯。因此第一列 ledger 只作 terminology-pending POC；不建立遊戲全域 glossary，
也不把外部英文／中文 patch 當原文來源。

## 下一個最小缺口

使用這一條 eligible row 建立 ignored local source／working record，跑
`restore_translations.rb`／`strip_translations.rb` 的 hash round-trip；再檢查既有
patch pointer/reinsertion 探針能否以一個 bounded UI row 做 dry-run。若回插格式仍
未證明，就只提交 ledger schema／negative receipt，不宣稱已能建置可玩的 ROM。

## M32 ledger／BPS dry-run receipt

已在私有目錄建立一列 source table 與 working record。`strip_translations.rb` 產生的
`games/tales-of-the-world-summoners-lineage/translations/m32-ui-row.jsonl` 只含
`source_locale`／`source_hash`，沒有 `source`；`restore_translations.rb` 以同一私有
source table 重建工作列，重算 SHA-256 仍為
`4055ab372bbb3feadbf21c328f0eb72e9ceb2874c8979383feb193eb722d4c60`。這是第一個
row-level source drift gate，target 仍是 `ai_draft`、terminology-pending，並非完整
翻譯帳本。

為確認 BPS／source-span 邊界而沒有偽造一個 target codepage，私有 dry-run 將 clean
ROM 複製成 byte-identical no-op target：`0x1FA4B4` bounded stream hash 為
`ba5fcf40ea248f9662571951de19c7447854d76f069091ed5b6f845d2b149d88`，兩者均為
8,388,608 bytes、SHA-256 `b41c293f…6186cfdd3`。`core/patches/bps_create.rb` 產生
29-byte BPS（SHA-256
`11d2a23e4cda81c85f5389089f0426cd40ed73f0ed640acc3cbd81161f88834e`），
`bps_apply.rb` 產出與 clean ROM byte-for-byte 相同的 8 MiB image。

這個 BPS receipt 只證明 ledger／patch plumbing 與 source span 定位；它沒有改變任何
ROM byte，也沒有證明目標 Latin／中文 code units、字型槽位、長度配置或 real
reinsertion。真正的 text write gate 仍關閉，下一個最小缺口是取得可驗證的 target
codepage／encoder 與固定槽位或 relocation policy，再做一個有實際變更且可重抽取的
私有 POC。

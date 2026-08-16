# A9PJ M1.9 keyboard gate／單一 transfer receipt（2026-08-16）

本切片只保留可審核的執行期 metadata、雜湊、watch 位址、PC/LR 與 DMA 欄位。ROM、
RAM／VRAM raw、圖片與 mGBA 暫存 build 均留在 `/private/tmp`；沒有建立 source table、
work ledger、翻譯或 ROM 回插。

## 嚴格執行邊界

- ROM 身分固定為 `TOW SUMMLINE`／`A9PJ`／`AF`／8 MiB，SHA-256
  `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- 每個 receipt 都用本 session fresh mGBA、`127.0.0.1:39123`、一個 GDB connection；
  上一個 process 完成後才停止並重開下一個自己的 process。
- `m19_gate_transfer_probe.py` 重用 `core/gba/gdbstub_client.py` 的 checksum／ACK
  parser，但把 request 序列化，設定 packet delay `0.12 s`、timeout `8 s`、retry
  limit `1`。data／register response 長度不符時直接 abort，不把延遲 payload 當成
  stop 或資料；continue／interrupt 不走 request retry。
- gate 階段只掛 `KEYINPUT=0x04000130` read watch；transfer 階段再加一個且僅一個
  asset watch。沒有寫入遊戲 state、tilemap 或 VRAM。

## Gate 重現

以既有 M1.5 的 bounded sequence `START, START, A` 作為導航上限（最多三步），每一步
都在按鍵後讀取 BG0/BG1 metadata。清楚的 gate 必須同時滿足：

1. `DISPCNT=0x1B40`、`BG1CNT=0x0106`（4bpp、charbase `0x4000`、screenbase `0x0800`）；
2. 八個固定五十音排列位置的 tile ID 為 `[1,2,3,4,5,27,28,29]`；
3. BG1 screenblock hash 與兩個既有鍵盤 tile hash 均一致。

三個獨立 clean mGBA run 均通過這個 gate：一個 gate-only、一個 `TILE1` write-watch
transfer run、一個 DMA3 control-watch transfer run。gate-only 的 pre-screen 是
`DISPCNT=0x1640`／`BG1CNT=0x0105`，第一個 `START` 後即為：

| 欄位 | receipt |
| --- | --- |
| `DISPCNT`／`BG1CNT` | `0x1B40`／`0x0106` |
| BG1 screenblock SHA-256 | `5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b` |
| selected position match | `8/8` |
| tile 1／tile 2 SHA-256 | `b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2` /
  `924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7` |

另有一個較早的 `START, START` clean navigation 只到 `DISPCNT=0x1F40`／非鍵盤畫面；
它被保留為 navigation negative，不拿來否定已成功的 gate。兩次 listener readiness／
second-connection failure 沒有 GDB request，不計入 clean gate 失敗次數。

## CPU／BIOS tile write negative

在一個 fresh process 的 pre-screen（`DISPCNT=0x1640`）後，最後 transition 前同時只保留
KEYINPUT read watch 與 `0x06004020`、長度 `0x20` 的單一 write watch。最終畫面仍通過
上述 gate，tile 1 hash 由 blank-stage 的
`66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925` 變成已知
keyboard hash，但 asset write watch hit count 為 `0`。

這是「該 transition 沒有被 CPU／BIOS 以可見 32-byte write watch 捕捉」的 bounded
negative，不是「沒有 consumer」；DMA 或更早／不同寬度的搬移仍可能存在。reset-stage
hash `02d449a31fbb267c8f352e9968a79e3e5fc95c1bbeaa502fd6454ebde5a4bedc` 永遠單列，
沒有與 keyboard tile hash 混用。

## DMA3 單一 setup/control watch negative

在另一個 fresh process、同一個 gate transition，只把 asset watch 改為 DMA3
`CNT_H=0x040000DE`（仍保留 KEYINPUT 作導航）。一筆 stop 的回報地址落在相鄰的
DMA3 count setup window `0x040000DC`；它不能被誤寫成精確 `CNT_H` enable caller，故
receipt 的 watch identity 標為 setup/control window。stop register metadata 如下：

| 欄位 | receipt |
| --- | --- |
| observed stop／requested watch | `0x040000DC`／`0x040000DE` |
| writer PC／LR | `0x08000616`／`0x080005D5` |
| CNT_H read at stop | `0x8400`（enable bit set，但尚未證明資料欄位可信） |
| source／destination | `0x78517851`／`0x78517851`（不屬 GBA 可讀 ROM/RAM/VRAM 來源） |
| count／decoded byte count | `0x0000`／`0x40000`（DMA3 count-zero maximum，不能當成實際 keyboard transfer） |
| tile hash at stop／after single-step | `66687aad…`／`66687aad…` |
| tile hash after bounded settle | `b5ae444…`（keyboard gate 成立） |
| source tile hash／byte-identical match | 無／`0` |

single-step 後與 settle 後 source/destination 仍是非 GBA 可讀的 mirrored-looking
values，`CNT_H` 也回到不 enable 的 `0x0400`；沒有可信 source pointer、destination
window、byte count 或 source bytes hash。因此這筆只能證明一個 DMA3 setup/control
觀察點，不是 source→VRAM transfer receipt。M1.8 的 queued DMA 欄位不被沿用。

## Identity／renderer 結論

| 對象 | M1.9 狀態 |
| --- | --- |
| BG1 keyboard gate | confirmed as screen/layout/hash gate，三個 clean run |
| `0x06004020` CPU／BIOS write transfer | precise negative，hit `0` |
| DMA3 source→destination→VRAM | unknown／protocol-and-address negative，未取得可信 receipt |
| `0x005E`／`0x0066` font-record path | 仍 provisional；M1.7 `0x080063C7` shared caller 未被本切片命中 |
| Unicode／日文 glyph identity | confirmed `0` |
| control code | 未證明 |

因此不能把 keyboard gate、tile hash 或 DMA setup stop 當作 codepage、source row 或
翻譯依據。下一個最小缺口是從已確認的文字 consumer／RAM code unit 路徑建立只含
metadata 的日文 record extractor，並以乾淨 ROM 的可重抽取 hash 對齊；BG1 asset DMA
仍應維持獨立候選，除非後續取得 byte-level source receipt。

## 可重現命令

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m19_gate_transfer_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --mode gate --port 39123 \
  --sequence start,start,a --max-steps 3 \
  --dump-dir /private/tmp/tow-a9pj-m19-gate --output /private/tmp/tow-a9pj-m19-gate/summary.json

PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m19_gate_transfer_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --mode transfer --asset-watch tile1 \
  --port 39123 --sequence start,start,a --transfer-index 0 \
  --dump-dir /private/tmp/tow-a9pj-m19-tile --output /private/tmp/tow-a9pj-m19-tile/summary.json

PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m19_gate_transfer_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --mode transfer --asset-watch dma3 \
  --port 39123 --sequence start,start,a --transfer-index 0 \
  --dump-dir /private/tmp/tow-a9pj-m19-dma3 --output /private/tmp/tow-a9pj-m19-dma3/summary.json
```

M1.9 完成的是可重現的 gate 與精確 negative 邊界，不等於翻譯完成；source table、
ledger、控制碼與回插仍關閉。

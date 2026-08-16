# A9PJ M1.7 font-record → VRAM consumer 切片（2026-08-16）

本切片只追蹤已在 M1.6 觀察到的 `0x005E`、`0x0066`。它不重做 startup
logo baseline，也不建立 source table、work ledger 或翻譯 row。ROM、sav、完整
RAM／VRAM、rendered PPM 與 JSON receipt 均留在 `/private/tmp`；Git 只保留本文件的
metadata、雜湊、位址與可重跑工具。

## 執行範圍與可重現性

| 欄位 | 值 |
| --- | --- |
| ROM | `A9PJ`／`TOW SUMMLINE`／`AF`，8 MiB |
| ROM SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| mGBA／GDB | 本 session 專用 `mgba-headless`，`127.0.0.1:39123` |
| private receipt | `/private/tmp/tow-a9pj-m17-runtime-final/summary.json` |
| input | `A` → `0x005E`、`RIGHT`、`A` → `0x0066`；KEYINPUT active-low、寫入 `r1` |
| termination | `bounded-trace-complete` |

工具先確認既有 keyboard gate 才注入按鍵：`DISPCNT=0x1B40`、`BG1CNT=0x0106`、
BG1 `screenbase=0x0800`、`charbase=0x4000`，八個選定 tile ID 為
`[1,2,3,4,5,27,28,29]`。這使 BG1 的鍵盤位置與文字 consumer 的 VRAM 目的地可
分開比較，而不是把轉場畫面變化當成字形寫入。

## BG1 圖層交叉證據

共用 `core/gba/capture_runtime.py` 取得 final runtime capture，再以
`core/gba/render_vram.py` 分別渲染 BG1 tilemap（private PPM hash
`5d3d3e85368fc0a6403f9a18909d78f8136bd0dd5f731dde7072a359b8a3f351`）與 VRAM
`0x2000` slice 的 raw grid（private PPM hash
`47c7c524fa24fc5264e3d51366a675a9efa707eb5fd1bbcc9060bf5b8b0904f6`）。圖片不進 Git。

`A/RIGHT/A` 前後的畫面／tilemap metadata 沒有改變：

| receipt | BG0 screenblock SHA-256 | BG1 screenblock SHA-256 | `a-row-1` tile | `a-row-2` tile |
| --- | --- | --- | --- | --- |
| before | `e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661` | `5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b` | `b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2` | `924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7` |
| after | `e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661` | `5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b` | `b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2` | `924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7` |

BG1 `0x06004020`（tile 1／鍵盤第一格）與 `0x06004040`（tile 2／鍵盤第二格）各設
32-byte one-shot write watchpoint，`tile_watch_hit_count=0`。因此本次沒有 CPU、DMA
或 BIOS 對這兩個 BG1 tile range 的直接命中；前後 hash 相同也排除了本次按鍵把它們
改成另一個 tile 的情況。

## 已證實的 code unit → font record → CPU VRAM consumer

M1.6 的 caller arithmetic `0x08089E00 + code_unit * 0x18` 在本次以 ROM read
watchpoint 再驗證。watchpoint 命中後先移除，再讀取 24-byte record 只產生 hash，避免
read watchpoint 因診斷 `m` packet 自我觸發。

| code unit | record bus address | record SHA-256 | read stop | observed PC／LR |
| ---: | ---: | --- | --- | --- |
| `0x005E` | `0x0808A6D0` | `aeac7e6ca436cfd8533f3171e8ddb3e790601dde94b1f7bedc5cfff3b9cad741` | `T05rwatch:0808a6d0;` | `0x08004A3E`／`0x080063C7` |
| `0x0066` | `0x0808A790` | `207f45437ff6d4c5fae7598547f0b89c6670991689cd64f44ea26f87b320b964` | `T05rwatch:0808a790;` | `0x08004B18`／`0x080063C7` |

靜態 Thumb path 對應為 `0x08004A3A` 與 alternate branch 的 `0x08004B16`
`ldrh r2,[r1]`；mGBA receipt 的 PC 是 memory access stop 後的觀察值，不能把它誤寫成
另一個 caller。兩個 record 都實際被同一個 `LR=0x080063C7` 的 renderer caller 消費。

renderer 的兩個直接 CPU store 點是：

| PC | Thumb instruction | 證據意義 |
| ---: | --- | --- |
| `0x08004C82` | `str r0,[r2,#0x20]` | formula 產生的第一個輸出 word；完成一次指令後讀 tile hash |
| `0x08004D1A` | `stm r3!,{r0}` | 同一 renderer 的後續 pointer-walk 輸出；不是獨立 DMA |

本次 bounded `A/RIGHT/A` 共收到 44 個 store breakpoint；與兩個目標 code unit 對應的
穩定結果如下。`store_offset` 是相對於該次 renderer formula base 的位移；第二個
`stm` 已經在函式內走過指標，不能拿當下的 `r3` 直接與原始 formula base 比較。

| code unit | formula base | CPU store address／offset | post-store tile SHA-256 | writer／LR |
| ---: | ---: | --- | --- | --- |
| `0x005E` | `0x060020C0` | `0x060020E0`／`0x20` | `e4e4d7a2c175ff1948a21042c922cddeb99f8b003060ec9e8d21e99c7d0de26b` | ROM CPU／`0x080063C7` |
| `0x005E` | `0x060020C0` | `0x06002320`／`0x260` | `4f7234b450f09d6c001ed82c962bc5ffd5633ce43eb7013208fe196fe88e3e6c` | ROM CPU／`0x080063C7` |
| `0x0066` | `0x060020E0` | `0x06002100`／`0x20` | `316efab5906d81656c22df3b35e82fc7fc6f1022b345ac5288434d0453450b96` | ROM CPU／`0x080063C7` |
| `0x0066` | `0x060020E0` | `0x06002340`／`0x260` | `136fb23c046f15a3a312ff8f1f693b88c5be609558e216c86852a306b0914ef0` | ROM CPU／`0x080063C7` |

這組目的位址落在 VRAM `0x06002000` 附近，屬於 BG0 `charbase=0` 所在的 VRAM
slice；它不是 BG1 的 `charbase=0x4000`（`0x06004000`）或本次選定的
`0x06004020`／`0x06004040`。因此 M1.7 已證實的是「font record → CPU glyph
consumer → 非 BG1 的 VRAM tile」，不是「font record → BG1 鍵盤格」。

## DMA／BIOS 分類

本次另對 DMA3 control `0x040000DC` 設 bounded write watchpoint，命中一次：

| phase | PC／LR | writer class | control write 後 source／destination／count-control |
| --- | --- | --- | --- |
| `a:0` | `0x080005FC`／`0x080005D5` | CPU game ROM | `0x20022002`／`0x20022002`／`0x04000000` |

這是 DMA3 register setup 的觀察，不含 `0x0808A6D0`／`0x0808A790` record pointer，也
沒有指向 `0x06004020`／`0x06004040`；不能把它宣稱為文字 DMA。control write 前的
`0x78517851` 是 stale register receipt，已在工具中與 after-write 值分欄。所觀察的
record read、store 與 DMA control writer PC 全部在 game ROM；本切片沒有 BIOS-range
(`0x00000000`–`0x00003FFF`) 的 copy 命中。這只排除本次已觀察路徑的 BIOS copy，不排除
其他 DMA channel、其他畫面或尚未走到的 BIOS helper。

## identity／控制碼門檻

| code unit | record read | font→VRAM consumer | BG1 keyboard position／hash | M1.7 status |
| ---: | --- | --- | --- | --- |
| `0x005E` | confirmed | confirmed CPU store，但目的為 `0x060020xx/0x060023xx` | no position／no hash match | provisional |
| `0x0066` | confirmed | confirmed CPU store，但目的為 `0x060020xx/0x060023xx` | no position／no hash match | provisional |
| 其他 code units | 未追蹤 | 未追蹤 | 未追蹤 | unknown |

本切片的 confirmed glyph identity 為 `0`、provisional 為 `2`、unknown 為其他未取樣
units。三方 gate（table arithmetic、runtime tile bytes/hash、BG1 keyboard position）
沒有同時成立，所以不建立 source-table POC；codepage 與控制碼仍是獨立未證明項目，沒有
開始翻譯或建立 ledger。

### M20 correction boundary

上表是 M1.7 當時以 BG1 tile-byte equality 為唯一 identity gate 的歷史判定。M20
`m20_keyboard_codepage_probe.py` 之後以實際 name-entry table 確認 row 0 前五項，
所以 keyboard identity 維度可獨立寫成 `0x005E=あ`、`0x0066=う`；本文件的
`M1.7 status=provisional` 仍正確描述 renderer store 到 same-time screen bytes 的
未完成 transfer gate，不應解讀成否定 keyboard table mapping。

## 工具與重跑

`tools/m17_font_tile_probe.py` 重用 `core/gba` GDB client／capture，新增：

- 0x18 record address arithmetic 與 2-byte ROM read watchpoint receipt；
- 兩個 renderer CPU store breakpoint、`r12-0x18` record pointer、context formula 與
  post-store tile hash；
- BG1 tile range negative watchpoint；DMA3 control write 前／後寄存器；CPU／DMA／BIOS
  writer class 分欄；
- 只輸出 counts、offset、registers、hash 與 provenance，raw 仍由 `--dump-dir` 寫入
  ignored／`/private/tmp`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m17_font_tile_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 39123 \
  --dump-dir /private/tmp/tow-a9pj-m17-runtime-final \
  --output /private/tmp/tow-a9pj-m17-runtime-final/summary.json
```

下一個最小缺口是定位 **BG1 keyboard 資產初始化本身** 的 source／DMA／copy：要在
keyboard transition 前後對 `0x06004020`／`0x06004040` 的上游 source buffer 或實際
DMA channel 做一次更窄的 setup watch，並證明它與 `0x005E`／`0x0066` 的 record path
有共同 caller；在那之前不得把這次非 BG1 consumer 當作鍵盤 glyph identity 或通用
codepage。

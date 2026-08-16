# A9PJ M1.5 執行期 name-entry／glyph 切片（2026-08-16）

本紀錄是一次有界的執行期切片，不保存 ROM、sav、VRAM／WRAM／OAM／palette raw、
渲染圖片或完整日文原文。所有 raw 與 PPM／PNG 都留在 `/private/tmp`；提交內容只保留
雜湊、寄存器、顯示參數、位址關係與陰性 receipt。

## 範圍與 ROM

- ROM：A9PJ，title `TOW SUMMLINE`，size `8,388,608` bytes。
- SHA-256：`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- mGBA：只使用本 session 的暫存 build 與 `127.0.0.1:23901`；每次 GDB client 連線
  結束後停止／重啟的都是同一個 A9PJ process。
- 工具：遊戲專屬腳本只負責 A9PJ identity、KEYINPUT 注入與候選 tile；GDB transport、
  標準 capture 與 BG／OAM renderer 來自 `core/gba/`。

## 導航與實際文字圖層

先以已證實的 KEYINPUT read path 做按鍵注入，不重新把 startup logo 當成取樣畫面。
此前一個有界 read watchpoint stop 是 `T05rwatch:04000130;`，`pc=0x08001E12`、
`lr=0x08060681`、`r0=0x04000130`、idle read value 在 `r1=0x000003FF`。讀值目的
暫存器因此確認為 `r1`；idle 是 active-low `0x03FF`。本切片使用 `r1` 覆寫
`START=0x03F7`，每次 18 個 hold event、6 個 release event。

重現序列是 `START, START, A`，在第二個 display／VRAM change 停止。shared capture
摘要得到：

| 狀態 | `DISPCNT` | `BG0CNT` | `BG1CNT` | `BG2CNT` | `BG3CNT` | VRAM SHA-256 前綴 | 判定 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| input 前 | `0x1F40` | `0x0000` | `0x0105` | `0x020A` | `0x830E` | `e3ad8be1` | 初始執行期狀態 |
| 第 1 個 `START` 後 | `0x1640` | `0x0000` | `0x0105` | `0x028A` | `0x830E` | `b52a5857` | title／演出圖層，僅作導航 anchor |
| 第 2 個 `START` 後 | `0x1B40` | `0x0000` | `0x0106` | `0x028A` | `0x030F` | `353cc01e` | 第一個互動 name-entry／kana 畫面 |

對最後一列使用 `core/gba/render_vram.py` 的 tilemap renderer，以及
`core/gba/render_oam.py --mapping 1d`，輸出只放 `/private/tmp/tow-a9pj-m15-menu2/`。
由 GBA BG register 反解並以圖層分開檢查：

- BG0：4bpp，charbase `0x0000`，screenbase `0x0000`；可見入口文字與下方分類標籤。
- BG1：4bpp，charbase `0x4000`，screenbase `0x0800`；可見假名輸入格。
- BG2：8bpp，charbase `0x8000`，screenbase `0x1000`；最後 `DISPCNT` 未啟用，沒有
  把它的前一畫面圖形當成 name-entry 文字。
- BG3：4bpp，charbase `0xC000`，screenbase `0x1800`；可見紫色鍵盤框與按鍵區。
- OBJ：1D composite 只見游標／小型元件；本切片沒有把 OBJ 判成文字 consumer。

這是「文字相關圖層」的畫面證據，不是日文 source row 證據；renderer 顯示出的假名只
用來確認畫面語境，沒有把整個畫面轉錄進 repository。

## Glyph addressing、identity、codepage、控制碼分離

選定 BG0 tilemap 座標 `(x=1, y=17)` 的第一個分類標籤 tile 作為最小追蹤目標：

| 證據維度 | 結果 | 狀態 |
| --- | --- | --- |
| glyph addressing | tile ID `0x125`；4bpp cell 位址 `0x06000000 + 0x125*0x20 = 0x060024A0` | **已定位畫面 cell** |
| tilemap context | 由 BG0 `0x0000/0x0000` renderer 重建，位於下方分類標籤起始位置 | **已定位語境候選** |
| glyph identity | 32-byte cell 與 clean ROM file offset `0x163184`（bus candidate `0x08163184`）有 exact match | **只證明 byte／圖形候選，不等於字元身份** |
| codepage／16-bit code unit | 沒有取得 source buffer、讀值序列或 code unit→glyph 對照 | **未確認** |
| 控制碼 | 沒有取得 parser／終止／換行／插值消費證據 | **未確認** |
| text consumer／caller | 本切片沒有合法的 tile write 或 source read stop | **未確認** |

`0x163184` 因此只能作交叉索引，不能拿來產生 `source.text`、codepage 表或翻譯
ledger。tile ID／VRAM address、ROM byte match、字元身份與控制碼在後續 decoder 中仍須
分欄保存。

## 有界 watchpoint receipt

### 第二個 `START` 的 transition trace

`m15_trace_text_tile.py` 在 title anchor 後設定：

- `Z2,60024a0,1`：1-byte VRAM write watchpoint。
- `Z3,4000130,2`：KEYINPUT read watchpoint，24 個事件（18 hold＋6 release）。
- 每個 stop 最多等待 3 秒；不再延伸到其他按鍵或事件。

結果為 `termination=completed`、`key_events=24`、`tile_hit_count=0`；最後畫面仍是
`DISPCNT=0x1B40`／BG0-BG1-BG3 的 name-entry 狀態。也就是第二個 `START` 改變了顯示
層選擇／VRAM 整體 hash，但沒有在這段時間由 CPU 寫入選定 tile cell。

### 從初始 GDB stop 的 boot trace

為排除 tile 在更早資源初始化時已搬入的可能性，`m15_trace_boot_tile.py` 從初始
`S02`（`pc=0`）即設定同一個 `Z2,60024a0,1`，只允許 8 秒 runtime budget。結果為：

- `termination=watchpoint-timeout`、`tile_hit_count=0`。
- budget 到期後的 `S02` 是 client 發出的 interrupt，不是 tile watchpoint stop。
- final capture 的 `DISPCNT=0x1F40`、`BG1CNT=0x0105`、`BG2CNT=0x020A`、
  `BG3CNT=0x830E`；沒有取得寫入 PC/LR。

這兩段 receipt 都沒有文字 consumer／caller，因此不能把任何 GDB stop 宣稱成文字
渲染函式。它們是可重跑的有界陰性結果，並且保留「第二次轉場未寫入」與「初始 8 秒
未由 CPU 寫入」兩個不同 scope；不代表 DMA、未選定 cell 或其他 source buffer 已被
排除。

## 可重現命令

先以本 session 自己的暫存 mGBA build 在 23901 啟動 A9PJ；ROM／sav／build 不進 Git：

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
DYLD_LIBRARY_PATH=/private/tmp/tow-mgba-build.CMuO3Y/build \
/private/tmp/tow-mgba-build.CMuO3Y/build/sdl/mgba \
-g /private/tmp/project-atlantis-a9pj.gba
```

導航／capture：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m15_navigate_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 23901 \
  --sequence start,start,a --stop-after-changes 2 \
  --dump-dir /private/tmp/tow-a9pj-m15-menu2 \
  --output /private/tmp/tow-a9pj-m15-menu2/summary.json
```

transition 與 boot watchpoint：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m15_trace_text_tile.py \
  /private/tmp/project-atlantis-a9pj.gba --port 23901 \
  --settle-seconds 5 --step-settle-seconds 1 --event-timeout 3 \
  --hold-events 18 --release-events 6 --max-tile-hits 4 \
  --dump-dir /private/tmp/tow-a9pj-m15-trace \
  --output /private/tmp/tow-a9pj-m15-trace/summary.json

PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m15_trace_boot_tile.py \
  /private/tmp/project-atlantis-a9pj.gba --port 23901 \
  --event-timeout 8 --max-hits 1 \
  --dump-dir /private/tmp/tow-a9pj-m15-boot-trace \
  --output /private/tmp/tow-a9pj-m15-boot-trace/summary.json
```

renderer 的 raw input 必須只來自上述 ignored／private dump；本次使用 BG0 `0x0000/0x0000`、
BG1 `0x4000/0x0800`、BG3 `0xC000/0x1800` 的 4bpp tilemap 與 OBJ 1D composite。

## source table／ledger gate

M1.5 已確認第一個互動畫面、實際 BG 圖層與一個 glyph cell 的 address，但沒有 source
buffer、code unit、控制碼或 text consumer stop。因此 source table 仍只有規格文件，
work ledger 仍維持空白；下一個 decoder／watchpoint 必須先取得上述缺失證據，才可建立
少量日文 row，更不能先開始大量 `zh-TW` 翻譯。

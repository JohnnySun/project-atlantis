# A9PJ M40 headless keyboard gate／code-unit correlation（2026-08-16）

M40 是一個有界的唯讀 runtime polling receipt。它重用本機既有的 headless mGBA
Lua bridge，不改動 mGBA source，也不使用另一個 session 的 GDB listener。腳本只
送出按鍵、讀取寄存器／EWRAM／VRAM／BG1 tilemap，raw log 與 Lua 腳本均留在
`/private/tmp`；本文件只保存 counts、hash、位址與可重跑的驗證界線。

## 固定輸入與 gate

- ROM：A9PJ，SHA-256
  `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- runtime：既有 `/private/tmp/atlantis-mgba-headless-build/mgba-headless`；沒有
  `-g`，避免碰到其他 session 所有的固定 GDB port `39123`。
- 按鍵序列：使用 Lua frame callback 在 fresh process 送出兩次 START、A、RIGHT、A、
  RIGHT、A；每次只維持一 frame，下一 frame 釋放。
- 觀測範圍：`DISPCNT=0x04000000`、`BG1CNT=0x0400000A`、EWRAM
  `0x02004014/0x02004016`、BG1 screenbase `0x06000800`，以及 BG1 charbase
  `0x06004020/0x06004040` 各 32 bytes。

frame 1500、2100、2700 均穩定得到：

| 欄位 | receipt |
| --- | --- |
| `DISPCNT` | `0x1B40` |
| `BG1CNT` | `0x0106`（charbase `0x4000`、screenbase `0x0800`） |
| 假名鍵盤 tilemap entries | `1001,1002,1003,1004,1005,101B,101C,101D`，`8/8` |
| tile at `0x06004020` | FNV-1a `E8F309FB`；SHA-256 `b5ae4440…c1ff39c2` |
| tile at `0x06004040` | FNV-1a `9F3322D9`；SHA-256 `924e2894…293c19f7` |
| scene stability | frame 1500→2700 未再發生 gate／tilemap 轉換 |

兩個 32-byte runtime tile 的 SHA-256 與 M19 已核對的 keyboard tile-1／tile-2
hash 完全相同；tilemap entry、系統假名排列與兩個 tile hash 因此在本輪同時成立。
這是 keyboard 畫面重現與 glyph asset identity 的 runtime corroboration，不是
CPU／DMA source-to-VRAM copy receipt。

## code-unit 與 renderer 分欄

同一 bounded run 由 `0x02004014/0x02004016` polling 得到：

| frame | EWRAM code units | scene |
| ---: | --- | --- |
| 662 | `0x005E`, `0x0001` | name-entry keyboard，首個選取位置 |
| 1202 | `0x005E`, `0x0062` | 同一 keyboard，向右一格後 |
| 1742 | `0x005E`, `0x0066` | 同一 keyboard，再向右一格後 |

這與既有 font-record arithmetic `0x08089E00 + code_unit*0x18` 一致地覆蓋
`0x005E=あ`、`0x0062=い`、`0x0066=う` 的已知 keyboard 排列；本輪只新增
runtime code-unit sequence／scene context，不把 `0x0062` 的同一張 32-byte tile
讀值誤當成新的 direct consumer proof。

M1.7 已有的 static font-record read／CPU BG0 store receipt 仍是另一條 renderer：
record read PC `0x08004A3E/0x08004B18`、LR `0x080063C7`，目的地落在 BG0
charbase `0x06000000`；M40 觀測的是 BG1 keyboard charbase `0x06004000`。本輪
沒有同一執行期的 shared caller、DMA source 或 CPU copy caller，因此兩條 path
維持 `independent-renderers-correlated-by-code-unit-only`，不合併 codepage。

## watchpoint／陰性界線

headless binary 未載入 debugger module；Lua API 回傳：

```text
ewram=-1  font-record-005e=-1  bg0-tile-005e=-1
```

frame callback 取得的 `PC=0x000001F8`、`LR=0x000000A4` 是 polling callback／idle
context，不是文字 consumer caller，故不列入 caller receipt。M40 沒有宣稱 reader
breakpoint、CPU write、DMA、BIOS copy 或 source→VRAM byte identity；這個 negative
只證明「在沒有 `-g` debugger 的 headless run 中，Lua watchpoint 無法註冊」，不是
「沒有 consumer」。

## 可重跑命令與結果

腳本與 raw output 均為私有檔案：

```sh
perl -e 'alarm 6; exec @ARGV' -- env \
  DYLD_LIBRARY_PATH=/private/tmp/atlantis-mgba-headless-build \
  /private/tmp/atlantis-mgba-headless-build/mgba-headless \
  -C logLevel=8 \
  --script /private/tmp/tow-headless-probe.lua \
  /private/tmp/project-atlantis-a9pj.gba \
  > /private/tmp/tow-headless-poll-m40.log 2>&1
```

本次在 alarm 邊界停止，process 已結束；未寫入遊戲 memory。可重現 assertions
為：ROM title/code `TOW SUMMLINE`／`A9PJ`、stable gate `3` 個觀測點、tile hash
`2/2`、keyboard position `8/8`、code-unit sequence `0x005E→0x0062→0x0066`、
watchpoint registration `0/3`。existing ledger-eligible rows 維持 `2`（M32/M34），
沒有新增 candidate、source table、translation row 或控制碼判定。

## 下一個最小缺口

M40 使 name-entry UI 的 runtime scene／code-unit gate 可重現，但仍沒有 direct reader
或 source→VRAM transfer receipt。下一步沿既有 46 筆 direct rows 與已確認的 consumer
metadata 做有限量 source／術語審核；只有另外取得獨立 non-UI scene 或 live control
consumer，才可擴大一般日文／CJK codepage。不得以 M40 的 polling callback 取代
reader／DMA 證據，也不得新增 M29+ 類型候選掃描層。

# GBA 執行期偵察工具

這裡收納不綁定遊戲的 mGBA／GBA 執行期工具。它們源自《光明之魂 1》已驗證的
GDB remote、VRAM 與 OAM 工作流，再吸收其他遊戲 session 實際遇到的相容需求。

遊戲的 ROM 身分、位址、文字格式、codepage、壓縮、指標與控制碼仍必須留在
`games/<game>/`；本目錄不能記錄任何一款遊戲的固定 offset 或格式假設。

## 工具

- `gdbstub_client.py`：mGBA 0.10.x 的最小 GDB remote client。支援暫存器、記憶體、
  breakpoint/watchpoint、continue/interrupt 與單一暫存器覆寫。
- `capture_runtime.py`：一次連線完成有界 runtime 基線；輸出暫存器、GBA I/O、
  VRAM/WRAM/OAM/palette 的 hash 與非零位元組數，也可把 raw dump 寫到 ignored 目錄。
- `render_vram.py`：渲染 regular BG tilemap、raw tile grid 或 Mode 3 framebuffer。
- `render_oam.py`：依 OAM 位置合成非 affine OBJ，支援 1D/2D mapping、4bpp/8bpp。

全部只使用 Python 標準函式庫，不需要安裝套件。

## mGBA session 規則

1. 每款遊戲使用自己的 mGBA process 與 GDB port，先以 ROM path、PID 和 listener
   交叉確認所有權；不可連線、停止或附加到其他 session 的 process。
2. mGBA 0.10.5 command-line `-g` 的預設 port 是 2345，而且該路徑在官方原始碼中
   固定寫死；`-C ports.*` 不會改變 CLI GDB stub。可在 Qt GDB 視窗指定 port，或只在
   `/private/tmp` 建立改過 port 的暫存 mGBA。不要把 mGBA source/build/port shim 提交。
3. 同一個 mGBA process 只建立一條 GDB client 連線。0.10.5 常在 client 斷線後無法
   正常接受第二條連線；要重連就只重啟自己那個 mGBA process。
4. `gdbstub_client.py` 已內建封包間隔與一次 timeout retry，不要在每款遊戲再重寫。
5. raw VRAM／WRAM／OAM／palette dump 只能放 `/private/tmp` 或
   `games/<game>/work/`。RAM 可能含原始遊戲文字，不可提交。

## 最短操作流程

先啟動屬於本作、已分配獨立 port 的 mGBA GDB stub。以下以 `24387` 為例；不要照抄
別人的 port。

確認連線與 CPU 狀態：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 core/gba/gdbstub_client.py \
  --port 24387 --run-seconds 0.5
```

一次擷取標準 GBA runtime 基線，將可能含原文的輸出留在本作 ignored `work/`：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 core/gba/capture_runtime.py \
  --port 24387 \
  --run-seconds 1 \
  --dump-dir games/<game>/work/runtime \
  --output games/<game>/work/runtime/summary.json
```

若要確認 GBA ROM entry 與首次 VRAM 寫入，可在同一條連線依序加入 breakpoint 與
watchpoint。`0x080000c0` 是 GBA cartridge entry，不代表任何遊戲的文字入口：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 core/gba/capture_runtime.py \
  --port 24387 \
  --breakpoint 0x080000c0 \
  --watchpoint 0x06000000 --watch-type 2 --watch-length 4 \
  --dump-dir games/<game>/work/runtime \
  --output games/<game>/work/runtime/summary.json
```

在遊戲專屬 Python 工具內引用 client：

```python
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient, parse_stop_watch

with GdbClient(port=24387) as client:
    print(client.request("?"))
    registers = client.read_registers()
    vram_head = client.read_memory(0x06000000, 0x200)
```

舊《光明之魂 1》client 常見名稱都有相容 alias：`send/request`、
`read_mem/read_memory`、`cont/continue_running`、`cont_and_wait/continue_until_stop`、
`clear_*/remove_*`、`parse_stop_watch/parse_watch_stop`。

## 從 I/O 判斷渲染參數

不要把 structured bytes 看起來像字型就當作字型。先讀 `DISPCNT` 與目標 `BGxCNT`：

- `BGxCNT` bits 2–3：charblock，VRAM offset = value × `0x4000`。
- `BGxCNT` bit 7：0 為 4bpp，1 為 8bpp。
- `BGxCNT` bits 8–12：screenblock，VRAM offset = value × `0x800`。
- `DISPCNT` bit 6：OBJ mapping，0 為 2D，1 為 1D。
- `DISPCNT` bits 0–2 = 3：Mode 3 bitmap，不使用 tilemap/palette 渲染。

Regular BG tilemap：

```sh
python3 core/gba/render_vram.py \
  games/<game>/work/runtime/vram.bin \
  games/<game>/work/runtime/palette.bin \
  --mode tilemap --charbase 0x4000 --screenbase 0xe800 --bpp 4 \
  --out games/<game>/work/runtime/bg.ppm
```

Raw charblock grid（只能用來看 tile，不代表字串排列）：

```sh
python3 core/gba/render_vram.py \
  games/<game>/work/runtime/vram.bin \
  games/<game>/work/runtime/palette.bin \
  --mode grid --charbase 0x4000 --bpp 4 --columns 32 \
  --out games/<game>/work/runtime/grid.ppm
```

Mode 3 framebuffer：

```sh
python3 core/gba/render_vram.py \
  games/<game>/work/runtime/vram.bin \
  --mode mode3 --out games/<game>/work/runtime/mode3.ppm
```

OBJ composite；完整 palette dump 中 OBJ palette 從 offset `0x200` 開始：

```sh
python3 core/gba/render_oam.py \
  games/<game>/work/runtime/vram.bin \
  games/<game>/work/runtime/palette.bin \
  games/<game>/work/runtime/oam.bin \
  --mapping 1d --out games/<game>/work/runtime/obj.ppm --verbose
```

## 證據邊界

- 靜態掃描只產生候選；runtime read/watchpoint 或 ROM-to-VRAM byte match 才能提高可信度。
- VRAM 首次寫入常只是 BIOS decompression/CpuSet，不能直接宣稱找到文字 renderer。
- tilemap 是 tile index/flip/palette bank，不是 pixel bytes；先由 BG register 分清
  charblock 與 screenblock。
- OAM naive tile grid 會打散多 tile 字元；需要看實際畫面時用 `render_oam.py`。
- GDB 記憶體/暫存器寫入只改 emulator runtime，不改 ROM，但仍須明確記錄用途；
  預設先做唯讀偵察。

## 驗證

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s core/gba/test -v
```

目前測試涵蓋 GDB packet、register/memory/point 操作、4bpp nibble 順序、tilemap flip、
Mode 3 與基本 OAM composite。實際遊戲的位址與畫面仍由各遊戲自己的研究紀錄驗證。

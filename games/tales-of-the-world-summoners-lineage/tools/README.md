# A9PJ 唯讀偵察工具

這些腳本只做本遊戲的結構偵察與工程差異統計，不是通用 GBA 解包器。它們不應把
ROM、patch、解壓資源或完整原文放入工作區的可提交路徑。

## 目前工具

- `scan_rom_layout.py`：標頭／雜湊、literal Shift-JIS sentinel、ASCII run、候選
  壓縮簽章、ROM 指標 run 與 entropy chunk。壓縮簽章明確標為 syntactic-only，
  不能單獨證明資料格式。
- `probe_resource_pointer_table.py`：對指定指標表逐項驗證 GBA LZ77／RLE，僅輸出
  tag、大小、錯誤與 sentinel 統計。
- `probe_text_pointer_layout.py`：掃描指向候選 16-bit little-endian 資料區的 ROM
  指標，輸出指標幾何與 NUL 終止統計，不輸出 code unit 或原文。
- `probe_patch_pointer_rewrites.py`：比較本機 clean／patched ROM 的對齊指標，輸出
  來源檔案 bucket 與新舊目標範圍，不輸出 pointed-to bytes。
- `probe_patch_payload.py`：追蹤外部 v0.20 patch 新增區的連續 LZ77 block 與 16-bit
  值統計，不輸出解壓內容。
- `disasm_code.py`：以 `/usr/bin/python3` 的 Capstone 反組譯指定 ROM 範圍；隨機資料
  的合法指令形狀仍需控制流或 runtime 證據覆核。
- `m15_navigate_probe.py`：M1.5 有界互動導航；在已證實的 A9PJ KEYINPUT read path
  上覆寫 r1 的 active-low 按鍵值，遇到第一個 display／VRAM 狀態變化即停止，並呼叫
  共用 `core/gba/capture_runtime.py` 的標準 region capture。輸出只含 hashes／寄存器／
  顯示參數；raw dump 必須放 ignored `work/` 或 `/private/tmp`。
- `m15_trace_text_tile.py`：從 title-logo anchor 導航到 name-entry，對 BG0 tile
  `0x125` 的 VRAM cell 設一個 byte write watchpoint，記錄 consumer PC/LR／寄存器與
  final BG/OAM capture；ROM offset `0x163184` 只作候選交叉索引，尚未宣稱 codepage。
- `m15_trace_boot_tile.py`：從初始 GDB `S02` 即對同一個 BG0 cell 設一個 byte write
  watchpoint，在固定秒數內檢查開機／資源初始化是否由 CPU 搬移該 cell；timeout 與人工
  interrupt 分開記錄，不把它們冒充 tile hit。
- `m16_keyboard_metadata.py`：解析已確認的 BG1 `0x4000/0x0800` 4bpp 假名鍵盤位置，
  輸出 tile ID、flip／palette、固定 stride、hash 與 clean-ROM exact-match offset；
  不把孤立 byte match 標成字元身份。
- `m16_name_entry_probe.py`：以 BG1 八格簽名自動停止在已知鍵盤，執行 `A, RIGHT, A`，
  做 EWRAM／IWRAM bounded diff，並可對明確 code-unit 候選設 one-shot writer／reader
  watchpoint。報告含 code unit、PC／LR／寄存器與 ROM font-record address math；完整
  RAM／VRAM 只寫 caller 指定的 ignored／`/private/tmp` dump。
- `test_m16_keyboard_metadata.py`：測試 tilemap 欄位／座標、diff／append filter 與
  0x18 font-record address arithmetic。

## 重現基準掃描

```sh
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/scan_rom_layout.py \
  <clean-A9PJ.gba>
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_resource_pointer_table.py \
  <clean-A9PJ.gba> --table-offset 0x4dfde4 --count 1333
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_resource_pointer_table.py \
  <clean-A9PJ.gba> --table-offset 0x1acf34 --count 520
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_text_pointer_layout.py \
  <clean-A9PJ.gba> --patched-rom <local-v020.gba>
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_patch_pointer_rewrites.py \
  <clean-A9PJ.gba> <local-v020.gba>
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_patch_payload.py \
  <local-v020.gba> --start 0x800000 --end 0x8537ce
```

`<local-v020.gba>` 是研究者在 `/private/tmp` 等本機暫存位置套用外部 IPS 後的檔案，
不是 repo input，也不應新增到 `games/.../roms/`。

## M1.5 bounded navigation

以下命令需要本 session 自己的 mGBA 在獨立 GDB port 監聽；`--sequence` 預設只嘗試
`START`、`A`、`B`，遇到第一個顯示／VRAM 改變就停止，不把改變自動標成文字。若已知
第一個 change 只是 title logo，可用 `--stop-after-changes 2 --sequence start,start,a`
略過它並捕捉下一個候選互動畫面：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m15_navigate_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 23901 \
  --dump-dir /private/tmp/tow-a9pj-m15-runtime \
  --output /private/tmp/tow-a9pj-m15-runtime/summary.json
```

`KEYINPUT` 是 active-low；本 A9PJ build 的 read stop 顯示目的值在 `r1`，但工具仍把
寄存器列為參數，並將每個 stop packet／PC／LR 記入本機摘要。顯示改變後，再依摘要中的
`DISPCNT`／`BGxCNT` 使用共用 `core/gba/render_vram.py` 或 `render_oam.py`，不要把
screenblock 當作 pixel 或把孤立 glyph 當成已知 codepage。

## M1.6 name-entry code-unit slice

這一切片不重做 startup logo baseline。工具會先讀 BG1 screenblock；只有在
`DISPCNT=0x1B40`、`BG1CNT=0x0106` 且八個已知 tile ID 都吻合時，才送出 `A, RIGHT, A`。
phase receipt、hash、watchpoint PC／LR 與負證據見
`../research/m16-name-entry-code-unit-20260816.md`。例如候選 buffer 的重跑命令如下：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m16_name_entry_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 39123 \
  --write-watch-address 0x02004014 --read-watch-address 0x02004014 \
  --dump-dir /private/tmp/tow-a9pj-m16-phase3 \
  --output /private/tmp/tow-a9pj-m16-phase3/summary.json
```

`0x02004014` 的 writer／reader 已由 runtime 命中，但 glyph identity 仍須同時通過
鍵盤位置、ROM exact match 與 table arithmetic；目前沒有 confirmed identity，因此不
建立 source table、work ledger 或翻譯 batch。

## M1.7 font-record to VRAM consumer slice

`m17_font_tile_probe.py` 不重做 startup baseline；先以既有 `DISPCNT/BG1CNT` 與八格
BG1 metadata gate 導航，再在 `A, RIGHT, A` 期間對下列分開觀察：

- `0x0808A6D0`／`0x0808A790` 的 2-byte ROM read watchpoint，完成後只留 24-byte hash；
- renderer 的 `0x08004C82 str r0,[r2,#0x20]` 與 `0x08004D1A stm r3!,{r0}`，由
  `r12-0x18` 還原 record pointer，並以 context formula／post-store 32-byte hash 取得
  實際 VRAM tile；
- BG1 `0x06004020`／`0x06004040` 的 32-byte write watchpoint，以及 DMA3 control
  `0x040000DC` 的前／後 register receipt；CPU game ROM、DMA 與 BIOS PC 分開分類。

本次 runtime receipt 證明 `0x005E`／`0x0066` 的 CPU consumer 寫入
`0x060020xx/0x060023xx`，不是 BG1 `0x060040xx`；BG1 watchpoint 為零且前後 hash
相同，所以兩者都是 provisional，沒有 source-table POC、控制碼證明或翻譯。完整結論見
[`../research/m17-font-record-to-vram-20260816.md`](../research/m17-font-record-to-vram-20260816.md)。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m17_font_tile_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 39123 \
  --dump-dir /private/tmp/tow-a9pj-m17-runtime-final \
  --output /private/tmp/tow-a9pj-m17-runtime-final/summary.json
```

## M1.8 BG1 asset provenance slice

`m18_bg1_asset_probe.py` 從 initial GDB stop 開始觀察 BG1CNT、BG1 charblock 的兩個
32-byte tile target 與 DMA0–3 control，接著以最多兩次 `START` 做 bounded transition。
它把 CPU／BIOS／DMA 分開保存 PC/LR、live pointer hash、register metadata 與 tile hash；
只有 keyboard tilemap signature、runtime tile hash 與可信 source copy 三者一致時才會
提高 identity。DMA source/destination 若遇到暫存 mGBA queued packet 或未對齊資料，會保留
protocol-limited status，不會把欄位當成有效 source。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m18_bg1_asset_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --port 39123 \
  --settle-seconds 5 --step-settle-seconds 0.75 --event-timeout 2 \
  --max-dma-hits 1 --dump-dir /private/tmp/tow-a9pj-m18-runtime \
  --output /private/tmp/tow-a9pj-m18-runtime/summary.json
```

`--watch-slice` 可把兩個 tile watch 改為 bounded `0x06004000–0x060040FF` 請求（若
stub 不支援則退回 `0x20`）。輸出只含 hashes／counts／offset／PC/LR／register
metadata；ROM、raw RAM／VRAM、rendered image 與完整原文必須留在 caller 的 ignored
或 `/private/tmp` 路徑。參考 negative receipt 與 M1.7 path comparison 見
[`../research/m18-bg1-asset-20260816.md`](../research/m18-bg1-asset-20260816.md)。

## 後續 decoder 約束

真正的 `decoder` 必須以日版 ROM 為輸入、產生被 `.gitignore` 排除的
`research/summoners-lineage-decoded.jsonl`，每行至少含 `string_id`、`locale`、
`text`、`provenance`。在 codepage／控制碼未確認前，只能輸出私有 code-unit 偵察
資料，不能把佔位猜測拿去建立翻譯 ledger；回插前必須以 clean ROM 重新抽取並驗證
source hash。

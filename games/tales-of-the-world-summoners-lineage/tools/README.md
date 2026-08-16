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
- `m19_gate_transfer_probe.py`：M1.9 嚴格序列化的 keyboard gate 與單一 transfer probe。
  `--mode gate` 只掛 KEYINPUT；`--mode transfer --asset-watch tile1` 只掛一個
  `0x06004020` 32-byte write watch，`--asset-watch dma3` 只掛 DMA3
  `0x040000DE` setup/control watch。回報只保存 BG1 metadata、hash、PC/LR、DMA
  source/destination/count/control 與精確 negative；不把 queued／非 GBA 位址當成
  source receipt。
- `test_m19_gate_transfer_probe.py`：測試 strict response 分類、gate hash gate、RAM/ROM
  region、reset hash 分離與 DMA3 destination window arithmetic。
- `m20_text_record_probe.py`：metadata-only 的 M2A record／codepage／control probe；
  重現 `0x08089E00 + unit*0x18`、整個 16-bit record table bounds、`0x080063B6`
  16-bit stream reader、`0x0000` terminator 與 `0xFF70` parser behavior candidate。
  pointer pool 只輸出 counts／stable candidate ID／hash，不輸出 code-unit sequence 或
  日文原文。
- `test_m20_text_record_probe.py`：測試 record arithmetic／bounds、row metadata、
  stream control classification、stable ID 與 codepage/control-code separation。
- `m20_glyph_screen_cross_probe.py`：把 M1.7 immediate CPU-store tile hash 與 private
  final BG0 VRAM／screenblock 對齊；只輸出 tile ID、座標、ink-mask hash 與 exact
  negative，不輸出 tile bytes／圖片／source。
- `test_m20_glyph_screen_cross_probe.py`：測試 GBA 4bpp mask、tile address、screen
  entry 與 keyboard label／renderer destination 的分離。
- `m20_keyboard_codepage_probe.py`：重現 name-entry `0x08052B94` 的
  `0x0808884C + 2*(row*65+selection)` table arithmetic，輸出 row 0 首五個已知
  mapping 的 code unit／record hash；不輸出 record rows 或一般 script source。
- `test_m20_keyboard_codepage_probe.py`：測試 65-entry row stride、little-endian
  table entry 與 keyboard identity／general stream mapping 的分離。
- `m20_text_callsite_probe.py`：掃描 `0x080063E0`／`0x0800638C`／`0x0800644C` 的
  Thumb BL callers，輸出簡單 argument provenance、ROM pointer stream hash／counts
  與 unclassified role；不輸出 stream bytes 或原文。
- `test_m20_text_callsite_probe.py`：測試 Thumb BL arithmetic、literal pointer provenance
  與 static candidate 的 scene/source 分離。

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

## M1.9 strict gate／single-transfer slice

M1.9 使用新 mGBA process 與單一 GDB connection；固定 packet delay `0.12 s`、timeout
`8 s`、一次 timeout retry，memory/register response 若長度或格式不符即 abort。導航
上限是既有 `START, START, A`，但以 BG1 keyboard signature 提前停止。gate 必須同時
符合 `DISPCNT=0x1B40`、`BG1CNT=0x0106`、八個位置 `8/8` 與 tile-1/tile-2 已知 hash。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m19_gate_transfer_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --mode gate --port 39123 \
  --sequence start,start,a --max-steps 3 \
  --dump-dir /private/tmp/tow-a9pj-m19-gate --output /private/tmp/tow-a9pj-m19-gate/summary.json
```

transfer mode 只能選一條狹窄 asset cohort；`tile1` 的 hit `0` 與 `dma3` 的 setup stop
均沒有可信 source→VRAM receipt。完整 hash／PC/LR／非 GBA DMA 欄位 negative 見
[`../research/m19-gate-transfer-20260816.md`](../research/m19-gate-transfer-20260816.md)。

## M2A text record／codepage metadata

在既有 M1.6／M1.7 runtime receipt 上，先重現不含 source 的 record／parser metadata：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m20_text_record_probe.py \
  /private/tmp/project-atlantis-a9pj.gba --candidate-limit 0 \
  --output /private/tmp/tow-a9pj-m20-text-metadata/summary-0x400.json
```

此命令的預設 pointer pool 只標為 `unclassified`；即使有 `0x0000` 或 `0xFF70`，也不
能自動建立 source row。M20 的完整 counts／hash／PC provenance 見
[`../research/m20-text-record-codepage-20260816.md`](../research/m20-text-record-codepage-20260816.md)。

M1.7 private capture 的 BG0 screen cross-check：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m20_glyph_screen_cross_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  /private/tmp/tow-a9pj-m17-runtime-final/summary.json \
  /private/tmp/tow-a9pj-m17-runtime-final/vram.bin \
  --output /private/tmp/tow-a9pj-m20-glyph-cross/summary.json
```

這次可重現四個 destination tile 與 BG0 screenblock 座標的對齊，但 final VRAM 與
immediate post-store hash 有三筆不同；因此 `0x005E`／`0x0066` 仍是 provisional，
不能把 rendered grid 或 tilemap 幾何誤標為 byte-identical glyph identity。完整 receipt
見 [`../research/m20-glyph-screen-cross-20260816.md`](../research/m20-glyph-screen-cross-20260816.md)。

`m20_text_runtime_probe.py` 是下一個 bounded runtime reader probe：`null-entry` 只掛
`0x080063E0`，`fixed-read` 只掛 `0x080063B6`，可選用既有 keyboard navigation；
navigation 會明確計數 KEYINPUT register writes，text window 只輸出 hash／counts。
目前 private reset→2 秒 `null-entry` capture 沒有命中，這只是否定該 startup window，
不是「沒有文字 consumer」的結論；fresh fixed-read 的另一輪在初始 protocol 階段
connection failed，也不列為 hit `0`。完整 bounded receipt 見
[`../research/m20-text-runtime-20260816.md`](../research/m20-text-runtime-20260816.md)。

下一步需在單一 fresh GDB connection 對 `0x080063E0`／`0x080063C2` 取得 bounded
stream pointer 與 runtime context，再開始本機 ignored `*-decoded.jsonl`；控制碼、
codepage mapping 與 glyph identity 尚未完成。

## 後續 decoder 約束

真正的 `decoder` 必須以日版 ROM 為輸入、產生被 `.gitignore` 排除的
`research/summoners-lineage-decoded.jsonl`，每行至少含 `string_id`、`locale`、
`text`、`provenance`。在 codepage／控制碼未確認前，只能輸出私有 code-unit 偵察
資料，不能把佔位猜測拿去建立翻譯 ledger；回插前必須以 clean ROM 重新抽取並驗證
source hash。

## M21 private candidate decoder

`m21_source_decoder.py` 已把上述 contract 做成可重跑的本機流程。它掃描 clean A9PJ
pointer candidates，重用 `0x0000` bounded stream／stable ID，從 name-entry table
產生已分欄的假名候選，並將未知 halfword 留成 `{Uxxxx}`、`0xFF70` 留成 `{FF70}`。
它只寫 caller 指定的 `research/*-decoded.jsonl`（已被 ignore），stdout 只有 counts／
ROM hash；每行固定 `runtime_context=false`、`scene_role=unclassified`、
`eligible_for_ledger=false`。row 0 首五個是 M20 confirmed mapping，其餘鍵盤序列是
provisional，不能當成一般劇情 codepage。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m21-decoder/summoners-lineage-decoded.jsonl
```

本輪 private receipt 是 8,066 個 pointer references、7,553 個 NUL 結尾 local rows；
其中 771 個沒有目前已知的 unresolved unit，但所有 rows 仍因 runtime/context 未分類而
不可進 ledger。完整 aggregate 與下一個 proof gate 見
[`../research/m21-private-decoder-20260816.md`](../research/m21-private-decoder-20260816.md)。

## M22 control-code candidate audit

`m22_control_code_probe.py` 只掃描 M20/M21 已定義的 bounded pointer candidates，並輸出
去重 target 的 stream count、unit frequency hash、top unit metadata 與 record class。它
將 `0x0000` terminator、`0xFF70` special-branch candidate、`0x0001` all-zero record
candidate 分欄；不輸出 halfword sequence、source text 或 glyph rows，且固定
`eligible_for_ledger=false`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m22_control_code_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m22-control/summary.json
```

## M23 private font renderer

`m23_font_render.py` 讀 `0x08089E00 + code_unit*0x18` 的 12 個 little-endian rows，
以 MSB-first 16×12 raster 產生 caller 指定的 PGM。`0xFF70` 僅作換行 layout candidate、
`0x0000` 僅作 bounded terminator；stdout 只有 dimensions／hash，PGM 與 OCR output 必須
留在 `/private/tmp` 或 ignored `research/*`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m23_font_render.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FA616 \
  --output /private/tmp/tow-a9pj-m23-render/candidate.pgm \
  --scale 4 --bit-order msb
```

M22/M23 都是 source-recovery preparation；沒有 runtime caller／scene proof 時，不能把
rendered glyph 或 OCR candidate 寫入 translation ledger。

## M24 direct caller candidate decoder

`m24_direct_callsite_decoder.py` 只保留 static Thumb BL callers 對
`0x080063E0` 的 ROM-literal `r2` stream，輸出 46-row local JSONL；比 broad M21 pointer
pool 更適合 private raster／context work，但仍固定 `runtime_context=false`、
`scene_role=unclassified`、`eligible_for_ledger=false`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m24_direct_callsite_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m24-direct/direct-decoded.jsonl
```

M24 private aggregate 與下一個 fresh runtime/context gate 見
[`../research/m24-direct-callsite-decoder-20260816.md`](../research/m24-direct-callsite-decoder-20260816.md)。

## M25 context-provisional mapping audit

`m25_context_mapping_probe.py` 只審計兩個尚未 confirmed 的候選：`0x000C→ー` 與
`0x00A8→ッ`。它輸出 table row／selection、record hash／ink count、bounded direct-caller
occurrence counts，並固定 `confirmed_identity_count_added=0`；不輸出 source text。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m25_context_mapping_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m25-context/summary.json
```

M25 的 `context-provisional` 不會覆蓋 M21 decoder 的 unknown map，直到取得 runtime 或
完整句子獨立 cross-check。

## M27 provisional direct decoder

`m27_provisional_decoder.py` 是 M24 direct caller JSONL 的 local-only overlay 版本，將
M25/M26 的 punctuation／small-kana candidates 加上明確 `mapping_status` 後輸出；未知
halfword 仍為 `{Uxxxx}`，每行固定 `runtime_context=false`、`scene_role=unclassified`、
`eligible_for_ledger=false`。即使某 row 暫時沒有 placeholder，也不能直接進 ledger。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m27_provisional_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl
```

## M26 keyboard punctuation audit

`m26_punctuation_probe.py` 對照 visible keyboard page 的 row 0 punctuation cluster：
`0x0006→・`、`0x0008→?`、`0x0009→!`、`0x000A→＿`、`0x000C→ー`、`0x000D→/`。輸出
table position、record hash／ink count 與 bounded direct-caller occurrence metadata，
所有 identity 固定為 `keyboard-layout-provisional`，不輸出原文或控制碼語意。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m26_punctuation_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m26-punctuation/summary.json
```

## M28 source checksum gate

`m28_source_checksum_probe.py` 驗證 private decoded JSONL 的 required fields、UTF-8
`source_text_sha256`、stable ID uniqueness 與 runtime／eligibility gate；它只輸出 counts／
IDs／hash mismatch，不輸出 source text。M27 的 46 rows 可通過 hash/schema，但因沒有
runtime-backed eligible row，`ledger_gate.open=false`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m28_source_checksum_probe.py \
  /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl \
  --output /private/tmp/tow-a9pj-m28-checksum/summary.json
```

## M29 runtime UI row cross-check

`m29_ui_row_cross_probe.py` 將 M27 direct row `caller=0x080526FE,
stream=0x1FA4B4` 與 M19 clean name-entry screen 的 BG0/BG1 hashes、`DISPCNT/BGxCNT`、
8/8 keyboard positions 及 private BG0 image hash 對照。基本模式只輸出 metadata，並明確
保留 `reader_breakpoint_hit=false`、`glyph_identity_confirmed_by_this_probe=0`、
`eligible_for_ledger=false`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m29_ui_row_cross_probe.py \
  /private/tmp/tow-a9pj-m27-provisional/direct-decoded.jsonl \
  /private/tmp/tow-a9pj-m19-gate-seq-1/summary.json \
  --bg0-image /private/tmp/tow-a9pj-m19-gate-seq-1/bg0-gate.png \
  --output /private/tmp/tow-a9pj-m29-ui/summary.json
```

M32 可在同一工具加入固定 known-screen receipt：`--rom` 讀 clean A9PJ 的 record／
bounded stream，`--bg0-vram` 只輸出五個 BG0 tilemap cell 的 entry／tile hash，
`--bg0-image` 只比較五個固定 component 的 1bpp mask，`--m17-summary` 只核對同畫面
screen／ROM metadata。它不寫出 source、glyph bytes、raw VRAM 或圖片；只有 ROM hash、
record hash、mask hash、tile hash、counts 與 gate fields 進 output。完整 M32 receipt 見
[`../research/m32-known-screen-raster-row-20260816.md`](../research/m32-known-screen-raster-row-20260816.md)。

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

M32 通過條件是 A9PJ／stream／terminator、5 筆 record hash、5/5 record-to-image mask、
BG0 tilemap／10 個 tile hash 與 BG1 8/8 gate 同時成立；它只將此 row 標為
`known-screen-record-raster-and-tilemap-correlated`、`glyph_identity_confirmed=5`、
`eligible_for_ledger=true`。`reader_breakpoint_hit`、general codepage、control schema
與 `raw_byte_copy_confirmed` 仍分別維持 false／未確認。

## M33 bounded target encoder／reinsertion POC

`m20_keyboard_codepage_probe.py --row 2 --count 52` 讀取 static Latin row；只有
`A`–`Y`、`a`–`y`、`Z`、`z` 的固定 table arithmetic 可供 bounded target POC 使用。
`--target-text` 只輸出 target encoder metadata，不輸出日文 source。中點 `0x0006`
在 M33 僅作 M32 row 的 preserved unit，不代表 punctuation codepage 已完成。

`m33_target_reinsertion_poc.py` 只接受 M32 caller literal `0x081FA4B4`，把 bounded
target stream append 到 image end，再將 file `0x52720` 的單一 literal 改為新 ROM bus
pointer；它會重新讀取 terminator、檢查 unresolved unit 與輸出 source-free receipt。
這是實際 byte-changing relocation POC，不是通用 encoder。target image／BPS 必須留在
`/private/tmp` 或 ignored work；BPS 建置與套用使用 `core/patches/bps_create.rb`、
`bps_apply.rb`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m33_target_reinsertion_poc.py \
  /private/tmp/project-atlantis-a9pj.gba --target-text '・Lester' \
  --output /private/tmp/tow-a9pj-m33-reinsert/target.gba \
  --receipt /private/tmp/tow-a9pj-m33-reinsert/receipt.json
```

M33 不會把 Latin static proof 外推成 CJK／一般 text stream codepage，也不會把沒有
GDB listener 的 mGBA run 當成 runtime QA。

## M30 `0xFF70` control/render cross-check

`m30_control_render_cross_probe.py` 只對既有 direct target 做 bounded control receipt：
確認 `0x0000` terminator、`0xFF70` 次數、M20 parser PCs 與私有 M23 PGM dimensions/hash。
它不輸出 source text，且只可確認 line advance；variable/name/item controls 與
`eligible_for_ledger` 保持 false。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m30_control_render_cross_probe.py \
  /private/tmp/project-atlantis-a9pj.gba 0x1FA616 \
  --image /private/tmp/tow-a9pj-m23-render/candidate-1-msb.pgm \
  --output /private/tmp/tow-a9pj-m30-control/summary.json
```

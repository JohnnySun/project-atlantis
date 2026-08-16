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

## 後續 decoder 約束

真正的 `decoder` 必須以日版 ROM 為輸入、產生被 `.gitignore` 排除的
`research/summoners-lineage-decoded.jsonl`，每行至少含 `string_id`、`locale`、
`text`、`provenance`。在 codepage／控制碼未確認前，只能輸出私有 code-unit 偵察
資料，不能把佔位猜測拿去建立翻譯 ledger；回插前必須以 clean ROM 重新抽取並驗證
source hash。

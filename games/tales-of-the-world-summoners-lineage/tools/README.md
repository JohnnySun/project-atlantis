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

## 後續 decoder 約束

真正的 `decoder` 必須以日版 ROM 為輸入、產生被 `.gitignore` 排除的
`research/summoners-lineage-decoded.jsonl`，每行至少含 `string_id`、`locale`、
`text`、`provenance`。在 codepage／控制碼未確認前，只能輸出私有 code-unit 偵察
資料，不能把佔位猜測拿去建立翻譯 ledger；回插前必須以 clean ROM 重新抽取並驗證
source hash。

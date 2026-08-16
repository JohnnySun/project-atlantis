# A9PJ 初始唯讀偵察（2026-08-16）

本記錄只保存可審核的結論與重現參數，不保存 ROM、完整原文、解壓資源或英文 patch
內容。暫存 ROM 與 patch 留在本機 `/private/tmp`，檔案不屬於 repository input。

## 基準與身分

本機從候選 ZIP 讀出單一 8,388,608-byte GBA image，解析結果如下：

- title `TOW SUMMLINE`、game code `A9PJ`、maker `AF`、software version `0`。
- CRC32 `9c534023`（與 ZIP entry CRC 一致）。
- MD5 `7bbd6798acfbe798d1e458938afc7a1a`。
- SHA-1 `c7bda17313fdef597ccec98502e71c7e61281c9b`。
- SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- ROM 內 header checksum `0x32`；依 GBA header bytes `0xa0..0xbc` 重算為 `0x64`，
  因此 `header_checksum_valid=false`。這是 dump 異常紀錄，不在本里程碑自行修補。

## 文字與資料區的負面／正面證據

`scan_rom_layout.py` 對完整 image 搜尋一組普通 UI／遊戲詞的標準 Shift-JIS bytes，
所有 sentinel 都是零命中。這只否定「未壓縮 literal Shift-JIS」這個簡單假設，不否定
日文文字存在。

`probe_text_pointer_layout.py` 以 file offset `0x1f0000..0x2c0000` 作候選目標區，
掃描 4-byte little-endian GBA 指標得到 8,066 個引用、6,705 個 distinct targets；
其中 6,338 個 target 在最多 0x400 個 halfword 內遇到 NUL。由於候選區含表格與二進位
資料，這些數字是「值得追蹤的 16-bit 資料候選」而不是 6,338 條已確認文字。

候選區內最大的連續引用 run 在 file `0x200f68..0x201264`，共 191 個 word；其他
可重現 run 包括 `0x87b34..0x87c90`（87）及多個 16／20／24／28-entry 的資料列。
run 的 monotonic 性不一致，故不能把所有 run 當成單一字串表。

## 壓縮與指標

以下兩張表不是猜測的 magic-byte 命中，而是逐項以 GBA LZ77（header `0x10`、flag
bit 7 → bit 0）驗證：

| table | entries | result |
| --- | ---: | --- |
| `0x4dfde4` | 1,333 | 1,333／1,333 valid LZ77，decoded size 32–2,048 |
| `0x1acf34` | 520 | 520／520 valid LZ77，decoded size 全為 512 |

兩表 target 都沒有標準 Shift-JIS sentinel；目前判定偏向圖像／字型／其他資源，不把
它們當文字池。`scan_rom_layout.py` 的全域壓縮 signature 掃描仍可能有大量二進位假陽性，
其輸出有 `syntactic_only=true` 與大小上限，只能作候選索引。

## 可重跑命令

```sh
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/scan_rom_layout.py \
  /private/tmp/project-atlantis-a9pj.gba > /private/tmp/a9pj-scan.json
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_resource_pointer_table.py \
  /private/tmp/project-atlantis-a9pj.gba --table-offset 0x4dfde4 --count 1333
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_resource_pointer_table.py \
  /private/tmp/project-atlantis-a9pj.gba --table-offset 0x1acf34 --count 520
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/probe_text_pointer_layout.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --patched-rom /private/tmp/project-atlantis-samorine-v020.gba
```

目前沒有把上述 JSON 複製進 repo；它們是可再生成的研究輸出。

## 執行期邊界

本里程碑尚未取得本遊戲自己 mGBA session 的畫面／VRAM／GDB stop 證據，因此不把
靜態指標、合法反組譯形狀或壓縮簽章寫成「遊戲實際讀到的文字」。下一輪可在獨立
GDB port 以 breakpoint／read watchpoint 追蹤候選資料的實際取用，並保存位址、讀取
大小、VRAM glyph 複製與 code unit 的最小證據。

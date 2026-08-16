# 《超級機器人大戰 D》漢化工作區

本目錄只處理日版 GBA《スーパーロボット大戦 D》（Project Atlantis slug：
`super-robot-taisen-d`）。翻譯目標是臺灣繁體 `zh-TW`；日文原文只在貢獻者自己的
合法 ROM、`research/` 與 `work/` 中作本機中間資料，不提交 ROM、完整原始腳本、
字型圖片或未授權的大段原文。

本遊戲採用 `docs/TRANSLATION-LEDGER.md` 的原文／譯文分離方案。可提交的翻譯檔
只能是 `translations/*.jsonl` ledger；`research/*-decoded.jsonl` 與 `work/` 是
本機資料。文字格式、碼頁、控制碼、指標、壓縮與回插器均須在本遊戲目錄內重新
證明，不能假定《黃金太陽》或《光明之魂》的格式可用。

## 基準 ROM

目前本機候選來自專案外層 ROM 收藏中的日版條目 `1120`，解壓後另存為本遊戲
自己的 ignored 路徑：
`roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba`。

截至 2026-08-16，ROM 身分已完成第一層交叉核對：

| 欄位 | 值 |
| --- | --- |
| GBA title | `SRWD` |
| game code | `A6SJ` |
| maker code | `D9` |
| software version | `00` |
| ROM 大小 | `8,388,608` bytes（8 MiB） |
| header complement | 儲存 `0x80`；依標頭計算 `0x80` |
| CRC32 | `efb45117` |
| SHA-256 | `12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84` |

重跑指令：

```sh
python3 games/super-robot-taisen-d/tools/fingerprint_rom.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --expected-game-code A6SJ --expected-crc32 efb45117
```

## 文字系統偵察狀態

詳細、可追溯的每輪紀錄在 [`research/recon-ledger.md`](research/recon-ledger.md)。
目前只把以下列為已觀察事實：

- GBA 標頭與 CRC／SHA-256 如上，尚未與另一份獨立 clean dump 做第二份 ROM
  bit-by-bit 比對。
- 在檔案 `0x076000..0x082490` 發現一個可重複辨識的靜態文字池：以 NUL 結尾、
  可用嚴格標準 Shift-JIS 解碼；目前從這段產生本機 2,325 筆候選 source record。
  這批資料可看到 debug、駕駛員／機體／武器名稱、UI、作戰目的、開場摘要與
  staff 等分區，但不代表已涵蓋話間或戰鬥對話。
- 4-byte 對齊的絕對 GBA ROM pointer 掃描，在同一文字池範圍找到 4,947 個命中、
  195 個連續群組，其中 4,137 個命中正好對應本機 source table 的字串 offset；
  這是文字池邊界與 ID／指標假說的靜態交叉證據，尚未等同於完整 renderer 呼叫鏈。
- 全 ROM 的結構性 Shift-JIS 掃描找到兩段高密度且單字唯一的字符序列：
  `0x7cb55c–0x7cc34a`（1783 字）與 `0x7dfb46–0x7e0366`（1040 字）。它們
  目前是字符表候選；尚未證明是遊戲共用 codepage，也尚未證明任何索引如何
  映射到渲染器。
- 全域直接搜尋常見選單詞本身很嘈雜；但上方有界文字池已用嚴格 Shift-JIS 與
  NUL 邊界逐筆重讀驗證。因此目前只確認「這個靜態文字池是直接 Shift-JIS」，
  不把結論擴張到尚未定位的劇情／戰鬥腳本。
- 4-byte ROM 指標掃描、BIOS 壓縮簽章掃描與 halfword-aligned `swi` 掃描均有
  大量候選；目前沒有任何候選同時具備可信呼叫鏈、資料邊界與實際文字內容，
  所以尚未宣稱未定位的文本使用哪種壓縮或指標表。靜態文字池的 pointer 命中
  已另列為有界證據，不取代 runtime／caller 驗證。
- 在 mGBA 0.10.5 的獨立 GDB session 中，ROM reset entry breakpoint 命中
  `pc=0x080000c0`，並以 VRAM write watchpoint 觀察到 `0x06000000` 的 runtime
  graphics transfer；這是可重現的執行／圖形消費者邊界陽性證據，不是文字 renderer
  或字型來源已證明。對文字池首字 `0x08076000` 設 read watchpoint，在 reset 後
  10 秒 bounded window 沒有命中；這只是否定該窗口內對「首字」的讀取，不能否定
  整個文字池被使用。完整 runtime 證據與限制記在 ledger。
- 回插路徑尚未證明。至少要先確認：文字記錄格式、控制碼／行寬、字符索引、
  字型來源、容量或擴容策略，以及從重建 ROM 再抽回的 byte-level 不變量。

可重跑的第一輪偵察工具：

```sh
python3 games/super-robot-taisen-d/tools/static_recon.py ROM
python3 games/super-robot-taisen-d/tools/scan_indexed_text.py ROM \
  --table-offset 0x7cb55c --table-count 1783 --show-text
python3 games/super-robot-taisen-d/tools/verify_sjis_source_table.py \
  ROM research/super-robot-taisen-d-decoded.jsonl \
  --start 0x76000 --end 0x82490 --expected-count 2325
```

`--show-text` 只把本機候選解碼輸出到終端，不應重導向到 Git 追蹤檔案。

後續 runtime 偵察優先使用共用 `core/gba/capture_runtime.py`、
`core/gba/render_vram.py` 與 `core/gba/render_oam.py`；本目錄既有的 GDB／記憶體
工具保留作本輪歷史證據，不再機械複製共用 packet、RAM／VRAM dump 或 renderer。

## 外部工程線索

2003 年的 NewWise／Robot Town《GBA-〈超级机器人大战D〉ROM修改篇》確認了遊戲
條目與部分機體／武器／精神資料的修改觀察，但沒有提供本專案可直接採用的文字
抽取、碼頁、控制碼或可逆回插規格；因此只作工程線索，不作翻譯來源：

<https://bbs.newwise.com/thread-9756-1-1.html>

## 里程碑

- [x] 建立遊戲專屬工作區、ROM fingerprint 工具與第一輪靜態偵察工具。
- [x] 核對日版候選 ROM 的標頭、CRC32、SHA-256 與 header complement。
- [x] 確認一個有界的靜態 Shift-JIS 文字池與其絕對 pointer 交叉命中。
- [x] 完成一次 bounded mGBA runtime boundary check：ROM entry／VRAM transfer 陽性，
  文字池首字 read watchpoint 陰性；未把它誤報成文字 renderer 證明。
- [ ] 確認完整文本分區、字串 ID／指標語意或池外結構。
- [ ] 確認字符表／字型格式、控制碼、行寬與分支腳本邊界。
- [ ] 輸出本機 `research/super-robot-taisen-d-decoded.jsonl`，並以 ledger 流程
  建立第一個小批次。
- [ ] 建立嚴格拒絕 source mismatch、缺字與控制碼不一致的編碼／回插器。
- [ ] 重抽取、BPS round-trip 與 mGBA 核心場景 QA。

目前尚未開始翻譯；完成的是可驗證的靜態文字／pointer 與 bounded runtime 邊界起點，
字型 identity、文字 renderer、控制碼與可逆回插仍未證明。

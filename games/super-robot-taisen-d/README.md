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
- M1.5 已用 `tools/classify_pointer_callers.py` 將有界池的 `4,947` 個 pointer
  references、`195` 個 pointer runs 與 `915` 個 Thumb literal candidates 分類，
  並以反組譯確認 pointer-table copy path 與直接 source-byte copy path。共用 core
  GDB runtime capture 在 `0x0800f49a` -> `0x08007e04` 命中 source
  `0x0807b3fc`、EWRAM buffer `0x02000d60` 與 bound `0x10`。
- 反組譯另確認 `0x08008724` 是逐字讀取並分流單／雙位元組的 text consumer，
  `0x080085fc` 做 codepage/glyph offset arithmetic，`0x080088c8` 做 glyph-base
  加法，`0x08008650` 寫入 tile buffer；受控 GDB trace 已走通這條鏈。這些是
  M1.5 的 addressing／consumer 證據，不能單獨當成字型來源 identity。
- M1.6 以 runtime slot `0x020131d0`（窄字）與 `0x020103ac`（寬字）設 write
  watchpoint，確認初始化 caller `0x08014e8c -> 0x080083a0`、writer
  `0x08008456`／`0x08008462`，以及兩個 nonzero ROM-mapped resource base
  `0x0814f664`／`0x08120dbc`。受控流程先完成初始化，再由 guard 放行
  `0x08008724` consumer；已用 strict source context 確認兩條 glyph identity
  chain：`0x0807b3fc` 的 `0x8983` → `ラ` 與 `0x0807b380` 的 `0xda88` → `移`。
  每條都交叉驗證 base+offset glyph bytes hash、`0x08008650` tile writer 與
  writer-output hash；最小 provenance map 在
  [`research/m16-glyph-provenance.json`](research/m16-glyph-provenance.json)，
  原始 runtime／cohort 輸出仍只在 ignored `work/`。
- M1.7 以 `0x08008724` consumer 的 bounded 靜態反組譯固定 NUL 終止、低位元組
  分流的 two-byte 窄／寬 glyph、沒有已證明的 single-byte glyph path、8／12 layout width、12／26 address stride 與
  `0x08008650` tile writer；沒有獨立 newline branch，ASCII／format-like pair
  與其他未知單位維持 opaque。2325/2325 source record 完成 tokenization→encode
  no-op byte-identical 驗證，其中 2189 筆是 glyph-only、136 筆拒絕為 opaque／
  unaligned。resource scan 的保守新增容量為窄字 165 個空白 addressable slot、
  寬字 0；這不是 Unicode identity 或完整 zh-TW 字型容量證明。
- M1.7 建立兩筆同長度（各 10-byte payload）的 fail-closed POC contract，固定
  source hash、token signature、line width、缺字、容量與變長拒絕條件；兩筆 no-op
  都保持含 NUL 的 byte identity。可審核 metadata 在
  [`research/m17-layout-boundary.json`](research/m17-layout-boundary.json) 與
  [`research/m17-poc-contract.json`](research/m17-poc-contract.json)，沒有開始
  翻譯、ledger 或 ROM 修改。
- M1.8 已在窄字 mode `0x080085fc` 固定 code-unit → slot 公式：resource
  `0x0814f664..0x08150fe4` 有 544 個 8×12／12-byte slot；完整 2325 筆 corpus
  只引用 257 個 slot，保護 3 個 blank-but-referenced slot 後，保守可分配容量為
  165 個。寬字新槽容量維持 0。allocator 只取 addressable、blank 且 corpus 未引用
  的窄字 slot，並拒絕 hash mismatch、collision、越界、wide／opaque／control、
  缺字、容量不足與變長輸入。
- M1.8 固定使用 repo 既有 GNU Unifont T-source 17.0.05（font SHA-256
  `c1768bd7...f46c5b53`，OFL-1.1 license SHA-256 `869692af...651763ded`），
  以明確的 16×16 → 8×12 static transform 產生 glyph。已完成一筆全窄、無專名、
  同長的 `string_id=526424` `ai_draft`：zh-TW target 為兩個窄字，配置 slot
  543／542；target 與相鄰 untouched record 都有 patched 前後 1bpp／4bpp
  render hash。完整 metadata 在 [`research/m18-narrow-poc.json`](research/m18-narrow-poc.json)，
  translation ledger 在 [`translations/m18-static-poc.jsonl`](translations/m18-static-poc.jsonl)。
- M1.8 static patched ROM 只改 target record 與兩個 glyph slot，共 28 bytes；
  BPS create/apply 已 byte-identical。ROM、BPS、render image 與 restored／working
  source 仍只留 ignored `roms/`／`work/`；runtime patched-screen proof、完整
  newline／layout、字型美術品質與批量翻譯仍 pending。
- 完整回插路徑尚未證明。至少要先確認：文字記錄格式、控制碼／行寬、字符索引、
  字型來源、容量或擴容策略，以及從重建 ROM 再抽回的 byte-level 不變量。

可重跑的第一輪偵察工具：

```sh
python3 games/super-robot-taisen-d/tools/static_recon.py ROM
python3 games/super-robot-taisen-d/tools/scan_indexed_text.py ROM \
  --table-offset 0x7cb55c --table-count 1783 --show-text
python3 games/super-robot-taisen-d/tools/verify_sjis_source_table.py \
  ROM games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --start 0x76000 --end 0x82490 --expected-count 2325

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/build_m16_cohort.py \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --pointer-report games/super-robot-taisen-d/work/pointer-caller-report.json --size 16 \
  --output games/super-robot-taisen-d/work/m16-source-cohort.jsonl

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/probe_font_resource.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --port 24567 \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --consumer-hijack --output games/super-robot-taisen-d/work/m16-font-runtime.json

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m17_layout.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --cohort-size 16 --output games/super-robot-taisen-d/work/m17-layout-report.json

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m17_poc.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --output games/super-robot-taisen-d/work/m17-poc-report.json

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m18_narrow_allocator.py seed-ledger \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --target-offset 0x080858 \
  --output games/super-robot-taisen-d/work/m18-seed-ledger.jsonl

ruby core/ledger/restore_translations.rb \
  games/super-robot-taisen-d/work/m18-seed-ledger.jsonl \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  games/super-robot-taisen-d/work/m18-static-poc-working.jsonl

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m18_narrow_allocator.py set-target \
  --working games/super-robot-taisen-d/work/m18-static-poc-working.jsonl \
  --output games/super-robot-taisen-d/work/m18-static-poc-working-final.jsonl \
  --zh-hans '没有' --zh-tw '沒有'

ruby core/ledger/strip_translations.rb \
  games/super-robot-taisen-d/work/m18-static-poc-working-final.jsonl \
  games/super-robot-taisen-d/translations/m18-static-poc.jsonl

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m18_narrow_allocator.py build \
  --rom games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --ledger games/super-robot-taisen-d/translations/m18-static-poc.jsonl \
  --working games/super-robot-taisen-d/work/m18-static-poc-working-final.jsonl \
  --target-offset 0x080858 --adjacent-offset 0x080860 \
  --patched-rom games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M18_static_poc.gba \
  --report games/super-robot-taisen-d/work/m18-static-poc-report.json \
  --render-dir games/super-robot-taisen-d/work/m18-renders

ruby core/patches/bps_create.rb \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M18_static_poc.gba \
  games/super-robot-taisen-d/work/m18-static-poc.bps
ruby core/patches/bps_apply.rb \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/work/m18-static-poc.bps \
  games/super-robot-taisen-d/work/m18-bps-applied.gba
cmp -s \
  games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M18_static_poc.gba \
  games/super-robot-taisen-d/work/m18-bps-applied.gba
```

`--show-text` 只把本機候選解碼輸出到終端，不應重導向到 Git 追蹤檔案。
最後一個 probe 須使用本 session 自己的 mGBA `-C skipBios=1 -C gdb.port=24567 -g`
進程；它會先驗證兩個 slot 非零，才執行 post-init consumer capture。自然選單／
queue 觸發尚未取代這條受控驗證。

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
- [x] M1.6 完成 font resource initialization 的 live slot writer／ROM resource
  pointer 證據，並以兩個 strict Shift-JIS source context 建立 glyph identity、
  glyph bytes hash 與 tile writer output hash 的最小可審核鏈。
- [x] M1.7 完成 `0x08008724` consumer 的 bounded token／終止／glyph class 分類、
  2325 筆 source 的 no-op byte-identical 統計、窄／寬 resource slot 容量盤點，
  以及兩筆同長度 fail-closed POC contract；newline、完整 layout 與 zh-TW
  Unicode capacity 仍維持 opaque／未證明。
- [x] M1.8 完成窄字 code-unit／slot formula、544-slot occupancy 與 165 個安全空槽
  allocator、12-byte glyph packing／固定字型來源 hash，以及一筆同長 static
  `zh-TW` glyph POC；target／相鄰 record、BPS round-trip 與 fail-closed gate 已
  通過，寬字新槽容量為 0，patched runtime screen 仍待驗證。
- [ ] 確認完整文本分區、字串 ID／指標語意或池外結構。
- [ ] 確認字符表／字型格式、控制碼、行寬與分支腳本邊界。
- [x] 輸出本機 ignored `research/super-robot-taisen-d-decoded.jsonl`，並以 ledger
  流程保留 source provenance；M1.8 已完成一筆 static `ai_draft` POC，批量翻譯仍未開始。
- [ ] 建立嚴格拒絕 source mismatch、缺字與控制碼不一致的編碼／回插器。
- [ ] 重抽取、BPS round-trip 與 mGBA 核心場景 QA。

目前尚未開始批量翻譯；M1.8 的一筆 static `ai_draft` 只證明窄字 allocator、同長
glyph POC 與 BPS round-trip，不代表完整文字覆蓋、newline／控制碼語意、zh-TW
字型美術品質、自然畫面 runtime 或完整可逆回插已證明。

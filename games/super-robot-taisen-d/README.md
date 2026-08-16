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
- M1.9 已建立 bounded runtime QA 工具與純 metadata 測試，並再次固定 target
  `string_id=526424` 的 source／ledger hash、NUL、4-byte payload、16px line width、
  slots `543/542` 與相鄰 `526432` 的 unchanged hashes。既有 M1.6 consumer path
  （`0x08008724` → `0x080085fc` → `0x080088c8` → `0x08008650`）仍是陽性；本輪
  兩次 clean restart 在自己的 port `24567` 進行一次 idle natural attempt，但
  GDB single connection 在 stop timeout 後無法再提供有效 packet response，因此
  patched target 的 M1.9 runtime 畫面／writer-to-cache proof 維持未觀察，不把
  transport negative 誤報成 ROM 或譯文失敗。證據在
  [`research/m19-runtime-qa.json`](research/m19-runtime-qa.json)；ROM、BPS、render
  與 probe output 仍只留 ignored `roms/`／`work/`。
- M1.10 以 `tools/m110_boundary_audit.py` 對同一個 source pool 完成 2325/2325
  ROM/source byte identity、NUL boundary、offset ordering／overlap 與 opaque-token
  統計：2189 筆可進 glyph-only no-op contract、136 筆 opaque／unaligned fail-closed；
  16-record cohort 也維持 no-op 16/16。newline-looking／未知 pair 仍只標為 opaque，
  研究摘要在 [`research/m110-boundary-audit.json`](research/m110-boundary-audit.json)，
  不代表完整 newline、speaker、multi-line layout 或池外文本已解出。
- M1.11 對 `0x08008724..0x08008A0C` 做 bounded instruction gate，固定 NUL exit、
  2-byte cursor、低位元組 `<=0x87` 的 8px／否則 12px width、`ceil(width/8)`
  tile-column 與 64-byte allocation unit；亦記錄 mode `==1` 與其他 helper branch，
  但不替 branch mode、speaker 或 newline 猜語意。完整結果在
  [`research/m111-layout-contract.json`](research/m111-layout-contract.json)，目前
  corpus 觀察最大 width 240／30 columns 不是引擎上限證明。
- M2 glossary slice 已建立 [`translations/glossary.zh-TW.tsv`](translations/glossary.zh-TW.tsv)：
  17 個 source-safe term entries 只保存 `string_id`、Shift-JIS raw hash、zh-TW
  候選、來源 URL 與決策記錄；12 個術語通過至少兩個社群來源，約修／莉姆、阿姆羅、
  拉・凱拉姆的 4 個用法衝突明確維持 deferred，另有 1 個 UI term provisional。
  `tools/m2_glossary_audit.py` 在 ignored local source table 上驗證 18/18 hash matches、禁止 kana/source-text
  外洩；摘要在 [`research/m2-glossary-audit.json`](research/m2-glossary-audit.json)。
  這只是術語準備，不是翻譯批次或回插批准。
- M2 batch-1 以 `restore_translations.rb` → ignored working → `strip_translations.rb`
  建立一筆 `string_id=526432` 的 `ai_draft` UI ledger，target 是同長兩窄字「存在」；
  static allocator 配置 slots `543/542`，target／font／adjacent render hashes、
  BPS create/apply byte-identical 均通過。`string_id=509548` 的「覺醒」候選因 source
  兩個 wide glyph 被 fail-closed 拒絕；寬字新槽容量維持 0。研究摘要在
  [`research/m2-ui-batch1.json`](research/m2-ui-batch1.json)，runtime screen 仍 pending。
- M3 已建立 [`tools/m3_reinsert.py`](tools/m3_reinsert.py) 的 bounded static reinsert
  contract：以兩筆 source-safe working ledger 做 global narrow allocation，重複 target
  codepoint 跨 record 共用 slot，並在 ROM／font／source hash、NUL、同長、control、
  capacity、collision、overlap gates 通過後輸出 ignored patched ROM。這次合併 POC
  配置 slots `543/542/541/540`，BPS 97 bytes apply byte-identical；研究摘要在
  [`research/m3-reinsert-contract.json`](research/m3-reinsert-contract.json)，不是完整
  encoder、wide-font 擴容或 runtime QA。
- `tools/m3_roundtrip_audit.py` 會重新讀取 clean／patched ROM 的 2325 筆 source pool，
  只輸出 base-source equality、target／untouched exact counts、hash 與 allowed diff
  ranges；它已對 M3 兩筆 POC 建立可重現的 2325/2325、2/2、2323/2323 comparator，
  不把此結果外推成完整劇情／戰鬥文本 round-trip。
- M4 前置 inventory 已由 [`tools/m4_corpus_inventory.py`](tools/m4_corpus_inventory.py)
  對同一個 clean ROM／ignored source table 完成 2325 筆 source-safe 結構分區；摘要在
  [`research/m4-corpus-inventory.json`](research/m4-corpus-inventory.json)。分區只依
  M1.7 已證明的 token shape，不命名語意：939 筆全窄 glyph-only、833 筆窄／寬混合、
  417 筆全寬、136 筆 opaque／unaligned；strict source／NUL／token encode no-op 都是
  2325/2325。窄字 reinsert 的結構入口因此精確限制為 939 筆，其他 1386 筆 fail-closed，
  寬字新槽容量仍為 0。這不等於話數／劇情分區，也不等於翻譯覆蓋。
- M4 wide reuse audit [`tools/m4_wide_reuse_audit.py`](tools/m4_wide_reuse_audit.py) 只
  允許重用 strict Shift-JIS source context 已建立的一對一既有 wide codepoint／slot：
  2325 筆 source 中有 743 個 identity、3983 次 occurrence，所有對應 24-byte payload
  都是已初始化 slot，新增 wide slot capacity 仍為 0。`U+79FB`／`0xDA88` 是 M1.6
  已有的 wide runtime positive；其餘 742 個是 static source-context only，不能冒充
  runtime proof。未在 map 的 target、wide font expansion 與 ROM 修改一律拒絕；摘要在
  [`research/m4-wide-reuse-audit.json`](research/m4-wide-reuse-audit.json)。
- M4 UI batch-2 選取另一筆同樣全窄、兩 unit、16px、NUL、無 control 的
  `string_id=512228`，以 restore→working→strip 建立 source-safe `ai_draft`「沒有」。
  它與既有 `526424`／`526432` 一起跑 M3 global allocator，兩個 target codepoint 都
  重用既有配置，沒有新增 unique glyph；摘要在
  [`research/m4-ui-batch2.json`](research/m4-ui-batch2.json)，ledger 在
  [`translations/m4-ui-batch-2.jsonl`](translations/m4-ui-batch-2.jsonl)。BPS／重抽取
  只作 static gate，runtime screen 仍 pending。
- M4 UI batch-3 再選 5 筆全窄、3 unit、24px、NUL、無 control 的一般 UI label，target
  為「類型：」「尺寸：」「資料：」「技能：」「完成：」。更新後的 `seed-ledger` 會從
  strict source shape 計算 `max_width=24`，不再把寬度寫死成 16；5 筆與前 3 筆合併為
  8-record global static reinsert，15 unique narrow glyph allocations，`U+FF1A` 跨
  record reuse。摘要在 [`research/m4-ui-batch3.json`](research/m4-ui-batch3.json)，
  ledger 在 [`translations/m4-ui-batch-3.jsonl`](translations/m4-ui-batch-3.jsonl)；
  BPS／re-extraction 通過，runtime screen 仍 pending。
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
  games/super-robot-taisen-d/tools/m110_boundary_audit.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --start 0x76000 --end 0x82490 --cohort-size 16 \
  --output games/super-robot-taisen-d/work/m110-boundary-audit.json

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
  games/super-robot-taisen-d/tools/m2_glossary_audit.py \
  games/super-robot-taisen-d/translations/glossary.zh-TW.tsv \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --output games/super-robot-taisen-d/work/m2-glossary-audit.json

# M2 batch-1 的完整 restore／target／strip／allocator／BPS 指令，見
# work/m2-ui-present-*（均為 ignored local artifacts）；tracked metadata 在
# research/m2-ui-batch1.json 與 translations/m2-ui-batch-1.jsonl。

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m3_reinsert.py \
  --rom games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --ledger games/super-robot-taisen-d/translations/m18-static-poc.jsonl \
  --working games/super-robot-taisen-d/work/m18-static-poc-working-final.jsonl \
  --ledger games/super-robot-taisen-d/translations/m2-ui-batch-1.jsonl \
  --working games/super-robot-taisen-d/work/m2-ui-present-working-final.jsonl \
  --patched-rom games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M3_batch_narrow.gba \
  --report games/super-robot-taisen-d/work/m3-batch-narrow-report.json

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/m3_roundtrip_audit.py \
  --base-rom games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --patched-rom games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M3_batch_narrow.gba \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --working games/super-robot-taisen-d/work/m18-static-poc-working-final.jsonl \
  --working games/super-robot-taisen-d/work/m2-ui-present-working-final.jsonl \
  --reinsert-report games/super-robot-taisen-d/work/m3-batch-narrow-report.json \
  --output games/super-robot-taisen-d/work/m3-roundtrip-audit.json

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
- [x] M1.9 完成 target／相鄰 static metadata、NUL／width 檢查、runtime QA 工具與
  test，並記錄兩次 clean restart 的 GDB transport negative；既有 consumer positive
  不外推為 patched target 畫面 QA。
- [ ] M1.9 follow-up 新啟動自己的 mGBA `24731`；launcher 成功但 unprivileged GDB
  socket 被 sandbox 拒絕，escalated probe 又遇 approval transport negative，沒有產生
  runtime evidence；不把它誤報成 ROM／譯文失敗。
- [ ] 本輪以自己 PID／port `2346` 對 patched M1.8 ROM 重新進行 controlled consumer：
  font-base nonzero guard 通過，但 target `0x08080858` 僅觀察到 1 個 codepage／narrow
  glyph event（static NUL record 預期 2 個），probe fail-closed；writer／tile hash
  與 screen proof 未產生。第二次 bounded trace 在 initializer 前停於 `S04/PC=0x4`，
  兩個 process 都已清理，均不解讀成 ROM／譯文失敗。
- [ ] 在新的獨立 mGBA process／port 完成 M1.9 patched target 與相鄰 record 的
  controlled writer/cache 或 VRAM hash proof；自然 menu／queue 仍不宣稱已達成。
- [x] M1.10 完成 2325 筆 source record 的 NUL／ordering／overlap／ROM equality
  audit、opaque／unaligned 分布、line-width 統計與 16-record bounded no-op cohort；
  unknown token 與 newline semantics 維持 opaque／未命名。
- [x] M1.11 完成 `0x08008724..0x08008A0C` 的 bounded layout instruction gate，固定
  NUL／two-byte／8-or-12px／tile allocation 公式與 mode branch 邊界；speaker、
  newline、完整多行與 branch mode 語意仍是 opaque。
- [x] M4 前置 structural inventory 完成 2325/2325 source／NUL／token no-op gate，
  並以 hash／offset／count metadata 分出 939 筆全窄、833 筆混合、417 筆全寬與
  136 筆 opaque／unaligned；不把這個格式分區命名成劇情語意。
- [x] M4 bounded wide reuse audit 完成 743 個既有 source-context identity 的一對一
  codepoint／code-unit／slot map；新增 wide slot、未映射 target 與 font expansion
  仍 fail-closed，runtime 僅有 `U+79FB` 的既有 bounded positive。
- [x] M4 bounded wide reuse contract 將 743-entry existing-slot map 做成 reject-closed
  policy：只接受已證明 identity，unknown target／new wide slot／font expansion 均拒絕；
  runtime confirmed 仍為 1，完整 wide resource strategy 尚未完成。摘要在
  [`research/m4-wide-reuse-contract.json`](research/m4-wide-reuse-contract.json)。
- [x] M4 bounded source provenance join 重用既有 pointer-caller report，保存 4,947
  pointer refs、915 literal candidates、609 exact source candidates／370 records 的
  source-safe caller／literal metadata；semantic labels 保持 `unclassified`，未擴張成
  話數／UI／分支語意。摘要在 [`research/m4-source-provenance.json`](research/m4-source-provenance.json)。
- [x] M1.12 建立 source-safe semantic/caller boundary：重用既有 4,947 pointer refs／
  915 literal candidates，對 609 exact source candidates 分成 123 個 caller cohorts，
  回傳前 32 個 bounded cohort 與完整 ID／instruction hashes；2325 筆 structural
  partition、2 筆 controlled runtime positive 與 exact-pointer overlap 分開保存。
  story／branch／battle／unit／UI、speaker、newline 與 engine width limit 均維持
  `unconfirmed`，沒有新增翻譯。摘要在 [`research/m112-semantic-caller-boundary.json`](research/m112-semantic-caller-boundary.json)。
- [x] M1.13 建立 fail-closed narrow＋runtime-confirmed-wide encoder contract：28 個
  已分配窄字、743 個既有寬字 identity（其中 1 個 bounded runtime-confirmed）均核對
  code-unit／slot collision、ROM／字型 hash 與容量；12 筆 tracked `ai_draft` ledger
  的 source hash、同長與窄字 encode 全數通過，2325/2325 source token no-op 通過。
  742 個 static-only wide、opaque/control、缺字、變長與 wide 新槽仍拒絕；這不是完整
  語意翻譯或完整 wide resource 策略。摘要在 [`research/m113-full-encoder-contract.json`](research/m113-full-encoder-contract.json)。
- [x] M1.14 將一次獨立 patched runtime trace 正規化為 fail-closed evidence：ROM hash 與
  font-base guard 通過，但 requested `0x08080858` 的預期 2-unit 消費實際觀察到
  `source_pointer=0x02018368`、`code_unit=0x628D`、codepage 1／glyph 0；即使有
  raw glyph-complete event，也拒絕當成 target render。修正 `m19_runtime_trace.py` 的
  bounded stack／entry setup 與 argument-match 判定；target writer／tile／screen 仍
  `not_proven`／`not_observed`。摘要在 [`research/m114-runtime-boundary.json`](research/m114-runtime-boundary.json)。
- [x] M1.15 對已知 `0x08008724` consumer 做 bounded executable callsite audit：在
  `0x08000000..0x08076000` 只檢查 direct Thumb BL／BLX 與 PC-relative literal；修正
  bounded disassembly 跨越前段 undecodable gap 後得到 direct `5`、literal `0`，
  register-indirect dispatch 仍 unresolved。`m115_caller_probe.py` 先前 invocation
  在執行前遇 approval transport negative，沒有把它誤記成 runtime positive；摘要在
  [`research/m115-consumer-callsite.json`](research/m115-consumer-callsite.json)。
- [x] M1.16 將 2325 筆 source 收斂成保守的 layout-safe static subset：NUL／strict
  token no-op 2325/2325；624 筆為 glyph-only narrow、單行、observed width `<=64px`，
  315 筆窄字但超過 cap、833 mixed、417 wide、136 opaque／unaligned 仍拒絕。64px
  是 POC allocation cap，不是 engine 最大寬度證明；newline／speaker／branch／變長
  仍 opaque/reject，沒有因此新增翻譯。摘要在 [`research/m116-layout-safe-contract.json`](research/m116-layout-safe-contract.json)。
- [x] M1.17 將既有 pointer-caller report 與全 corpus 做 source-safe coverage join：
  2325/2325 structural partitions、609 exact candidates／370 records、123 caller
  cohorts（309 anchored／300 unanchored）全數以 hash/count 覆蓋；各 partition 的
  exact pointer coverage 分開保存，story／branch／battle／unit／UI 與 natural caller
  仍 `unconfirmed`／`not_observed`。不重新掃描 pointer、不新增翻譯。摘要在
  [`research/m117-corpus-coverage.json`](research/m117-corpus-coverage.json)。
- [x] M1.18 將已驗證的 `0x08008724` consumer 與 2325 筆 source 統一成
  fail-closed control／layout contract：NUL terminator、two-byte narrow／wide glyph
  與未知 unit 的 opaque/reject policy；source／NUL／token no-op 均 2325/2325，並
  保存 narrow 11902、wide 3983、ASCII/format-like opaque 1032、unaligned tail 88
  的 source-safe metadata。consumer 沒有 dedicated newline branch，但 newline、speaker、
  branch 語意與 engine width limit 仍未證明；624 筆單行窄字 `<=64px` 只是保守
  static subset，不解除其他 partition 的拒絕。摘要在
  [`research/m118-control-layout-contract.json`](research/m118-control-layout-contract.json)。
- [x] M1.19 以新鮮自有 mGBA PID／port `2346` 與單一 GDB connection 捕捉到 patched
  ROM 的自然 consumer entry：font base nonzero、`0x08008724` 命中，LR／callsite 為
  `0x08066055`／`0x08066050`；bounded Thumb setup 證明 `r0<-r7`、`r1<-r5+0x400`、
  `r2=0x0D`、`r3=0x05`、stack arg `1`。runtime `r0=0x02018368` 是 RAM buffer，
  與 target `0x08080858` 不匹配，因此 target glyph／tile／screen proof 仍拒絕；摘要在
  [`research/m119-caller-reroute.json`](research/m119-caller-reroute.json)。
- [x] M1.20 對五個已確認 direct consumer callsite 做 bounded instruction-window
  inventory：`0x0800869E` wrapper fallback、`0x08008E1C` queue-entry drain、
  `0x08066050/62` dual-buffer UI、`0x0806E01C` indexed object buffer；每個窗口
  都有 static hash／trigger metadata。這些是結構分類，不是 story／branch／battle／
  unit／speaker 語意；全 corpus 仍 2325 筆、609 exact candidates／370 records／123
  cohorts，newline engine semantics、最大寬度、自然 screen 仍未證明。摘要在
  [`research/m120-semantic-caller-inventory.json`](research/m120-semantic-caller-inventory.json)。
- [x] M1.21 完成 source-safe wide identity／target encoder capacity join：wide resource
  `0x08120DBC..0x0814F664` 為 24-byte payload／26-byte stride、7332 physical slots，
  new-slot capacity `0`；743 個既有 identity 中只有 `U+79FB`／`0xDA88`／slot `905`
  有 bounded runtime confirmation，742 個 static-only 維持 reject。2325/2325 strict
  source／NUL／token no-op 通過；source class 為 narrow `11902`、wide `3983`、opaque
  `2152`。target map 分區為 12 筆窄字可接受、1250 筆含 static-only wide reject、927
  筆缺 identity、136 筆 opaque；147 個 source-wide occurrence 被 target narrow
  allocation 重新映射，與 resource class 分欄保存。摘要在
  [`research/m121-wide-encoder-capacity.json`](research/m121-wide-encoder-capacity.json)，
  工具在 [`tools/m121_wide_encoder_capacity.py`](tools/m121_wide_encoder_capacity.py)。
- [x] M1.22 對 patched M1.8 static POC 做一次 bounded fresh mGBA／GDB transport
  attempt：專用 port `24568`，sandbox socket 在連線前回報
  `operation_not_permitted_before_connection`，獲授權 probe 回報 `connection_refused`。
  自有 process 已乾淨停止；listener、font-base、`0x08008724` consumer、glyph lookup、
  tile writer、cache／VRAM 與 screen 均 `not_observed`，因此不把它當成 runtime failure
  或 target proof。source-safe target／adjacent hashes、base／patched／BPS hash 與
  M1.19 caller trigger 已收斂在
  [`research/m122-runtime-receipt.json`](research/m122-runtime-receipt.json)，建置工具
  為 [`tools/m122_runtime_receipt.py`](tools/m122_runtime_receipt.py)，測試為
  [`tools/test_m122_runtime_receipt.py`](tools/test_m122_runtime_receipt.py)。
- [x] M1.23 在既有 `0x08008724..0x08008A0C` consumer window 做 bounded control／
  semantic boundary：static disassembly 固定 source／render NUL exits、2-byte glyph
  loop、`[sp+0x5C]` 高 halfword→`cmp #1` routing field origin，以及 equal／other paths；
  沒有 `0x0A/0x0D` dedicated compare。2325/2325 source NUL／token no-op、opaque
  newline candidate `0`、opaque units `1120` 通過；observed width `0..240` 不是 engine
  limit，64px 仍只是 fail-closed static POC cap。newline／speaker／branch semantics、
  完整 line count 與 natural screen 仍 `unconfirmed`／`pending`。摘要在
  [`research/m123-control-semantic-boundary.json`](research/m123-control-semantic-boundary.json)，
  工具／測試在 [`tools/m123_control_semantic_boundary.py`](tools/m123_control_semantic_boundary.py)
  與 [`tools/test_m123_control_semantic_boundary.py`](tools/test_m123_control_semantic_boundary.py)。
- [x] M1.24 重用既有 pointer/callsite reports（不重掃 ROM）建立 source-safe caller／
  corpus coverage reconciliation：609 exact pointer candidates／370 records／123
  cohorts、5 個 verified direct consumer callsites；12 筆 tracked ledger 全部落在
  exact pointer records。各 structural partition 的 uncovered count、M1.19 RAM-buffer
  mismatch、M1.22 transport negative 與 natural caller `not_observed` 分欄保存；story／
  branch／battle／unit／UI／speaker／newline 仍 `unconfirmed`，不將 pointer 或 static
  ledger 命中外推成 scene coverage。摘要在
  [`research/m124-corpus-caller-coverage.json`](research/m124-corpus-caller-coverage.json)，
  工具／測試在 [`tools/m124_corpus_caller_coverage.py`](tools/m124_corpus_caller_coverage.py)
  與 [`tools/test_m124_corpus_caller_coverage.py`](tools/test_m124_corpus_caller_coverage.py)。
- [x] M1.25 修正 M1.22 的 GDB port 假設後，以本機 2348 build 做一次 fresh patched
  runtime attempt：只讀 source evidence 確認 `GDBStubListen(..., 2348, ...)`，但 process
  沒有 TCP 2348 listener／ROM descriptor，唯一 probe `connection_refused`；自己的
  process 已停止。font-base、consumer、glyph、writer、cache／VRAM、screen 都是
  `not_observed`，`rom_or_translation_failure=false`。source-safe receipt 在
  [`research/m125-runtime-transport-receipt.json`](research/m125-runtime-transport-receipt.json)，
  工具／測試在 [`tools/m125_runtime_transport_receipt.py`](tools/m125_runtime_transport_receipt.py)
  與 [`tools/test_m125_runtime_transport_receipt.py`](tools/test_m125_runtime_transport_receipt.py)。
- [x] M1.26 重跑既有 M1.13／M1.21／M4 contracts 並核對全部 12 筆 tracked ledger：
  source／token no-op `2325/2325`、ledger encoder `12/12`、same-length `12/12`、
  static reinsert target `12/12`、untouched `2313/2313` 均一致。coverage 仍是
  fail-closed subset：未翻譯 narrow `927`、mixed `833`、wide `417`、opaque `136`；
  wide static-only identity `742`、new-slot capacity `0`。報告只保存 hash/count/partition
  metadata，`full_semantic_translation=false`、`release_ready=false`；摘要在
  [`research/m126-full-encoder-ledger-audit.json`](research/m126-full-encoder-ledger-audit.json)，
  工具／測試在 [`tools/m126_full_encoder_ledger_audit.py`](tools/m126_full_encoder_ledger_audit.py)
  與 [`tools/test_m126_full_encoder_ledger_audit.py`](tools/test_m126_full_encoder_ledger_audit.py)。
- [x] M4 full-corpus fail-closed gate 重讀 2325/2325 source／NUL／token no-op，確認 12
  筆 ledger 可進窄字 static subset；927 筆窄字未翻譯、833 筆 mixed、417 筆 wide、136 筆
  opaque／unaligned 明確拒絕，`full_encoder_status=fail_closed_subset_only`。摘要在
  [`research/m4-full-corpus-gate.json`](research/m4-full-corpus-gate.json)。
- [x] M4 UI batch-2 完成 `512228` 的 restore／strip、duplicate-codepoint global
  allocation、BPS apply 與 2325 筆 re-extraction comparator；3/3 target、2322/2322
  untouched、runtime screen 仍 pending。
- [x] M4 UI batch-3 完成 5 筆 24px source-shape seed、restore／strip、15-slot global
  allocation、BPS apply 與 re-extraction comparator；8/8 target、2317/2317 untouched、
  runtime screen 仍 pending。
- [x] M4 UI batch-4 完成 3 筆 48／56px source-shape seed、restore／strip、26-slot
  global allocation、BPS apply 與 re-extraction comparator；11/11 target、2314/2314
  untouched、outside allowed ranges equal，runtime screen 仍 pending。工具與摘要在
  [`tools/m4_ui_batch4.py`](tools/m4_ui_batch4.py) 與 [`research/m4-ui-batch4.json`](research/m4-ui-batch4.json)。
- [x] M4 UI batch-5 完成 `516324` 一筆 64px source-shape seed、restore／strip、28-slot
  global allocation、BPS apply 與 re-extraction comparator；12/12 target、2313/2313
  untouched、outside allowed ranges equal，runtime screen 仍 pending。工具與摘要在
  [`tools/m4_ui_batch5.py`](tools/m4_ui_batch5.py) 與 [`research/m4-ui-batch5.json`](research/m4-ui-batch5.json)。
- [x] M2 glossary slice 完成 17 筆 source-safe zh-TW 詞彙 provenance：12 筆雙來源
  通過、4 筆衝突 fail-closed deferred、1 筆 provisional；工具測試涵蓋 source hash
  mismatch、kana 外洩、來源不足與 deferred 無 target。
- [x] M2 batch-1 完成一筆兩窄字 UI `ai_draft` 的 restore／strip、slot allocator、
  target／相鄰 static render、BPS round-trip；wide-glyph 精神指令候選明確拒絕，
  尚未做 patched runtime screen QA。
- [x] M3 bounded static reinsertor 完成兩筆窄字 ledger 的 global allocation、
  duplicate-codepoint reuse、strict reject gates 與 BPS round-trip；wide／opaque／
  newline／完整 corpus／runtime 仍未完成。
- [x] M3 bounded re-extraction audit 完成 clean／patched source pool 2325/2325 base
  equality、2/2 target exact、2323/2323 untouched exact 與 allowed diff-range gate；
  full corpus rebuild 仍未完成。
- [ ] 確認完整文本分區、字串 ID／指標語意或池外結構。
- [ ] 確認字符表／字型格式、控制碼、行寬與分支腳本邊界。
- [x] 輸出本機 ignored `research/super-robot-taisen-d-decoded.jsonl`，並以 ledger
  流程保留 source provenance；M1.8／M2／M4 已完成十二筆 static `ai_draft` POC，完整批量
  翻譯仍未開始。
- [x] 建立 bounded strict-reject source mismatch、缺字、控制碼、wide、容量、collision
  與變長的窄字編碼／回插器；完整 corpus、wide resource 與 runtime 仍待後續門檻。
- [ ] 重抽取、BPS round-trip 與 mGBA 核心場景 QA。

目前尚未開始完整批量翻譯；M1.8／M2／M4 的十二筆 static `ai_draft` 與 M2 glossary 只證明窄字 allocator、同長
glyph POC 與 BPS round-trip，不代表完整文字覆蓋、newline／控制碼語意、zh-TW
字型美術品質、自然畫面 runtime 或完整可逆回插已證明。

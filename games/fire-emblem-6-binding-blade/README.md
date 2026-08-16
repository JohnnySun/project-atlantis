# 《聖火降魔錄：封印之劍》日版（AFEJ）

本目錄只處理 GBA 日版《ファイアーエムブレム 封印の剣》（Fire Emblem: The Binding Blade）。原始 ROM 必須由貢獻者自行提供，僅放在被 Git 忽略的 `roms/`；本專案不保存 ROM、完整日文腳本、未授權字型或來源不明的大段原文。

## 目前狀態

截至 2026-08-16，已由使用者提供的本機日版 ZIP 唯讀解出一份 8 MiB ROM 到被忽略的 `roms/base/AFEJ.gba`，並完成 GBA 標頭、CRC32、SHA-1／SHA-256 與 `recon_afej.py` 核對。ROM 未加入 Git。

目前已由 AFEJ 執行期確認一條文字路徑：EWRAM 文字緩衝區會被字元消費者讀取，經兩位元組碼表查找後，glyph index 會寫入 EWRAM 渲染物件並進入 VRAM bitmap composer。完整劇情／支援／事件表、控制碼、glyph pool／tile stride／palette 對應與可逆回插仍未完成。

M1.5 已再確認一個有限 producer：ROM pointer table `0x080f635c[index 3087]` 取出 `0x080f2256`，經 copy／IWRAM worker 寫入 `0x02029404`，並在 renderer 實際觀察到 `0x01` marker 與 payload 後的 `0x00` 邊界。M1.6 已反組譯實際 loader entry `0x08013ad0`、IWRAM worker 的 ROM 初始化來源，並建立 `index 3080..3095` 的 16 筆 opaque-token corpus；16/16 decode→encode source bytes 相等，index 3087 的固定 buffer hash 也與獨立 runtime receipt 相等。source encoding、`0x01` 的換行／等待／結束語義及完整表格仍屬 provisional；沒有開始大批翻譯。

M1.7 已往上確認高階 caller：`0x08098afc` 以 selector 經 ROM table `0x08691738` 映射到 loader index，並在實際 `BL 0x08013ad0` callsite `0x08098b10` 觸發 index 3087。loader 的 copy-wrapper BL 真正起點是 `0x08013b02`；`0x08013b04` 是同一條 ARM7TDMI 雙半字 Thumb BL 的第二個 halfword，不能用來命名 caller 或解讀 LR。Start 可自然到達不同的顯示狀態，但 bounded 觀察沒有再次命中 `0x08013ad0` 或 `0x02029404` write-watchpoint，因此第二場景尚不能歸入 3342-entry table；`0x01` 仍是 opaque。

M1.8 已靜態枚舉 AFEJ 全 ROM 163 個合法、對齊的 ARM7TDMI 雙半字 Thumb BL direct callsites，分成 104 個 bounded prologue/return caller group。不同於 selector table 的最佳候選是 `0x080985d8`–`0x08098620` 內的 `0x080985ec`：函式先把參數 `r0` 存入 stack，再載回作為 loader index。自然 `KEYINPUT` 導航仍只重現 `0x08098b10`／index 3087；因此另以真實 Thumb loader stop 為 state seed，對 `0x080985ec` 做明確標記為 controlled 的 index 3086 probe，取得 `lr=0x080985f1`、`0x080f9394` → `0x080f2241`、EWRAM hash `beef794a…f9376e11`、terminator 31、`0x01` offset 12。第二 caller 的內容類別與 renderer 消費仍 unknown；`0x06014000` sink 本輪新 watchpoint 零命中，`0x01` 仍 opaque。

M1.9 已用三個 fresh mGBA／各自單一 GDB connection，僅透過 active-low `KEYINPUT` read-watchpoint 導航，完成三條 bounded natural route：`start,a`、`start,a,a,a`、`start,a,a,a,a,a,a,a,a,down,a,a,start,a`。三條都自然命中既有 selector `0x08098afc` → `0x08098b10` → index `3087`，沒有命中第二類 `0x080985ec` 或 `0x08098624`；每條都有 `0x08013ad0=1`、`0x08098b10=1`、第二 caller=0 的 hit-count、VRAM hash 與 display-register receipt。自然 consumer `0x08098c24` 實際讀取 `0x02029404`，`0x08098c78` 也命中控制分支；但本三條路徑均沒有命中 `0x08099424`、`0x080995b0`、實際 CPU `str r1,[r2]` 的 `0x080995a6` 或固定 sink watchpoint。這是精確 bounded negative，不把 M1.8 controlled probe 冒充自然 reachability；`0x01` 仍為 opaque，未建立 codepage 或語義分類。

M1.10 以同一個已驗證 tree worker 對 pointer domain `[0,3342)` 做 hash-only structural census。3203/3342 筆通過 decode→encode byte-identical 與相鄰 pointer span check；139 筆以明確的 `decoder_buffer_limit_no_terminator` 留在 negative corpus（第一筆 index 17），不把它們擅自當成另一種壓縮或文本格式。支援範圍的 marker record counts 為 `0x00=3203`、`0x01=1789`、`0x04=87`、`0xff=99`；`research/m110-table-census.json` 只含 index/provenance/hash/長度/marker counts，沒有 source bytes、code-unit bytes 或 Unicode。這是結構 coverage，不是劇情／支援／事件／資料表的語義分類；139 筆的專用 worker/格式缺口仍待 caller 與 runtime 證據。

M1.11 已把下一層 caller gate 收斂成可重跑的 static report：AFEJ 全 ROM 有 163 個合法 loader direct BL；非 selector 候選 `0x080985d8` 有 10 個 direct callers，另一候選 `0x08098624` 有 1 個（`0x0809837c`），已知 selector `0x08098afc` 有 8 個。ROM 內以對齊 word 搜尋到 Thumb callback pointer `0x08098341`（file offset `0x691230`）與 `0x080984a9`（`0x691358`），兩者都伴隨 ROM-pointer／scalar／zero 的固定鄰接形狀；這是 dispatch-like 結構候選，不是場景、內容類別或自然觸發證據。`0x08098340` 的上游 gate 仍需 runtime callback receipt，`0x01`、Unicode/codepage、回插與 139 筆 worker 缺口維持 unknown/opaque。

M1.12 以 fresh mGBA、單一 GDB connection 與只供應 active-low `KEYINPUT` 的 bounded route 重跑同一份 loader：selector `0x08098b10` → index 3087，接著自然命中另一個合法 direct callsite `0x08009252` 兩次 → index 2678、2679。兩筆的 LR 都由 `0x08013ad0` 回推為 `0x08009252`，並分別將 `0x080ecfd7`／`0x080ed003` 寫到 `0x02029404`；source-window hash 為 `2d410429…9965199`／`8fa20870…321d40d`，output buffer hash 為 `a93417f8…150df2`／`55cfb376…f0144df`，terminator 在 80／66，`0x01` 在 `[20,48]`／`[28]`。這確認同一 3342-entry domain 的第二自然 caller family，但不把 route 命名為章節、對話或資料表。M1.11 的 callback word read-watchpoint `0x08691230`／`0x08691358` 與 callback entry `0x08098340`／`0x080984a8` 都是 0；`0x01` 仍 opaque，Unicode/codepage、字型身分、ledger、回插與 BPS 未完成。

已確認的 ROM 身分與 runtime 位址、證據限制，見 `research/recon-20260816.md`。

公開 FEBuilderGBA 與 `fireemblem6j` 資料只作為待驗證的逆向參考，不取代日版 ROM，也不把既有英譯或 `.tbl` 當作翻譯來源。已知外部參考與其限制見 `research/recon-20260816.md`。

## 唯讀偵察

若要重跑本機唯讀偵察，執行：

```sh
python3 tools/recon_afej.py roms/base/AFEJ.gba --json-out work/afej-recon.json
```

若要重跑 M1.5 的 runtime receipt，先以獨立 mGBA GDB port `2346` 啟動本機 AFEJ，再執行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/capture_m15_producer.py \
  --port 2346 --timeout 30 --branch-hits 2
```

該工具只輸出位址、索引、雜湊、控制 marker offset 與 breakpoint／watchpoint 結果，不輸出完整 ROM、RAM 或原文。

若要重跑 M1.6 的 bounded extractor，使用本機被忽略的 ROM 與研究輸出：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/extract_afej_m16.py \
  --rom roms/base/AFEJ.gba \
  --output research/afej-decoded.jsonl \
  --runtime-receipt work/afej-m16-runtime-receipt.json
```

預設 cohort 是 `index 3080..3095`。每筆只保留 stable ID、pointer provenance、source/output hash、長度、leaf-derived code-unit／opaque token 與 marker offset；不使用 FE7／FE8 或外部 TBL 猜 Unicode。`research/afej-decoded.jsonl` 與 `work/afej-m16-runtime-receipt.json` 都是本機 ignored 產物。

要重新產生 index 3087 的 runtime receipt，先以自己的獨立 mGBA GDB port 啟動 AFEJ，再執行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/capture_m16_runtime.py \
  --port 23901 --timeout 30 \
  --output work/afej-m16-runtime-receipt.json
```

該 receipt 只保存 loader entry／table／source／worker／EWRAM 位址、breakpoint／watchpoint 停止點、buffer hash、長度與 logical marker offsets，不保存 ROM、RAM dump 或完整原文。

要重跑 M1.7 的 caller／場景收據，使用一次性自己的 mGBA GDB port：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m17_callers.py \
  roms/base/AFEJ.gba --port 23901 --sequence start,a \
  --output work/afej-m17-runtime.json
```

它只輸出 Thumb callsite／LR、selector/index/table/source provenance、EWRAM／VRAM hash、marker offset 與顯示寄存器摘要；按鍵輸入透過 `KEYINPUT` read-watchpoint 注入，`work/afej-m17-runtime.json` 維持 ignored。M1.7 的第二場景沒有命中 loader 或 EWRAM buffer write-watchpoint 是 bounded negative result，不是已完成的內容分類。

要重跑 M1.8 的全量 direct-callsite 靜態報告，不需啟動 mGBA：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m18_callers.py \
  roms/base/AFEJ.gba --static-only \
  --output work/afej-m18-static-calls.json
```

要重跑自然 caller／loader／renderer sink receipt，使用自己的 mGBA GDB port；`--no-display` 只略過昂貴的整屏 VRAM 讀取，仍保存每步 display registers：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m18_callers.py \
  roms/base/AFEJ.gba --port 23901 \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a \
  --no-display --watch-renderer \
  --output work/afej-m18-natural.json
```

若自然導航未到達不同 caller，可明確重跑 controlled probe；它會先等真實 reset 路徑進入 Thumb loader stop，再暫時跳到已確認的 `0x080985ec`，不把結果冒充自然場景：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m18_callers.py \
  roms/base/AFEJ.gba --port 23901 \
  --force-callsite --probe-index 3086 \
  --runtime-callsites 0x080985ec --max-records 1 \
  --watch-renderer \
  --output work/afej-m18-controlled-3086.json
```

M1.8 的完整 static JSON、runtime receipt 與任何 raw dump 都留在被忽略的 `work/`；提交只包含工具、測試與不含完整原文的研究方法／hash／位址摘要。

要重跑 M1.9 的三條自然 caller／consumer／動態 writer receipt，使用 fresh mGBA 與單一 GDB connection。工具只寫入 KEYINPUT read-watchpoint 所需的 `r1` 輸入值；不寫 selector、index、PC 或 game state。完整 VRAM 只保存 hash，建議報告放在 `/private/tmp`：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m19_natural.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25019 \
  --route-name menu-chapter-dialogue-long \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a \
  --output /private/tmp/afej-m19-route3.json
```

`--source-port` 是本機 loopback transport workaround，可避免多次 GDB session 後 ephemeral source-port 分配異常；它不改變 ROM 或遊戲執行語義。M1.9 的完整 route JSON 僅留在本機 ignored `/private/tmp`／`work/`，提交只保留工具、測試與 hash／位址／negative 方法摘要。三條自然路徑的下一個最小觸發缺口是從 `0x080985d8` 的 10 個 direct callers 或 `0x08098624` 的 `0x0809837c` 上游 state/menu gate 找到真正可達的 chapter/dialogue/load path；在此之前不做批量翻譯。

要重跑 M1.10 的完整 hash-only census：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m110_corpus.py \
  --rom roms/base/AFEJ.gba \
  --output research/m110-table-census.json
```

工具會對每個 pointer entry 嘗試既有 worker；不符合 `0x400` buffer/terminator 邊界的 entry 只記錄 failure kind，不輸出其解碼 bytes。`research/m110-table-census.json` 可提交作為結構研究摘要；任何完整 decoder/work corpus 仍留在 ignored 路徑。

要重跑 M1.11 的 static caller／callback gate report：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m111_gates.py \
  roms/base/AFEJ.gba \
  --output /private/tmp/afej-m111-gates.json
```

報告只保存 direct-call 數量、bounded function disassembly 摘要、index-source class 與 callback pointer 的位址／鄰接 word class；不輸出 ROM bytes、完整原文或 scene/category 命名。M1.11 的 callback pointer 只可作下一個 runtime gate 候選，不能把 controlled probe 當 natural reachability。

要重跑 M1.12 的 callback／第二 caller natural receipt，需先啟動本次專屬 mGBA GDB port，然後執行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m112_dispatch.py \
  roms/base/AFEJ.gba --port 23901 \
  --route-name m112-natural-generic-caller \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a \
  --output /private/tmp/afej-m112-natural-generic-caller.json
```

工具保存 callback pointer read／entry hit counts、loader LR/table/source/output hash、marker offsets 與 display I/O；`--sequence` 只注入 KEYINPUT，不寫 state、index、PC 或 ROM。M1.12 的 callback 0-hit 是 bounded negative；自然 `0x08009252` receipt 是第二 caller 證據，仍不等於內容分類或 Unicode。

M1.13 在同一工具加入 generic high-caller／renderer branch receipt：static scan 證明 `0x080117ba` 是 function `0x08011778` 內呼叫 `0x08009240` 的合法 Thumb BL，wrapper 內再於 `0x08009252` 呼叫 `0x08013ad0`。fresh route 實測 `0x08009240` 的 `LR=0x080117bf` → `0x080117ba`、loader 的 `LR=0x08009257` → `0x08009252`；renderer candidate breakpoints 全 0，只有既有 `0x08098c24` consumer 讀取。這完成 call-chain provenance，沒有替 `r0/r1/r2` 或 `0x01` 取語義名稱。

要重跑 M1.13 call-chain／renderer negative receipt，可使用固定 source port 避免本機多 session 的 ephemeral port 問題：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m112_dispatch.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25031 \
  --route-name m113-natural-callchain \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a \
  --output /private/tmp/afej-m113-natural-callchain.json
```

M1.13 的 renderer 0-hit 是 bounded negative；不要把 `0x08009240` 的 wrapper 或 generic route 的畫面狀態命名成章節／支援／對話，也不開始翻譯。

M1.14 再往上確認 generic high caller 的 function-pointer dispatch：static body 在 `0x0800e02a` `BL 0x0809df14`，而 `0x0809df14` 的 bounded entry instruction 是共用 `BX r1` thunk；table literal base 是 `0x085c4164`，以 `index*8` 查找。AFEJ static record 以 4-byte aligned word 唯一命中 `0x08011779` 於 file `0x5c4414`／GBA `0x085c4414`，index 86、flag `0x00000002`。fresh route 的 callsite 13 hits 中，2 筆實測 `r1=0x08011779`、index 86、entry pointer/flag 相符，隨後各命中 `0x08011778`；這是 function-pointer dispatch receipt，不是自然場景或內容分類。初次直接在共用 thunk 設 breakpoint 造成 1257 hits，已排除為 unbounded shared-thunk noise，正式 tracer 只停 callsite。

M1.14 同一路徑的 `0x085c4414`／舊 callback pointer read-watch 均 0，表示不能把 GDB ROM read-watch 當作 CPU 讀取證據；實際正證據是 static `BL`／`BX r1`、runtime `r1`、table index/entry/pointer 對應與 callback entry LR。renderer candidates 仍全 0，只有 EWRAM consumer branch；`0x01`、flag、Unicode/codepage、字型、回插與 BPS 仍 unknown/opaque。

M1.15 對 `0x02024750` 加上一次性 write-watch，取得第一筆 dispatch-object producer：watch stop PC `0x08003a1a` 的實際前一條 writer 是 `0x08003a18: str r1,[r0]`，static function boundary `0x08003a04–0x08003ad6`，其 allocator callsite `0x08003a0e` → `0x08003c54`。runtime `r1=0x08691858`、`r0=0x02024750`，after-value 也為 `0x08691858`；與 M1.14 的 table index/pointer receipt 分欄保存。這只是 object 初始化的一個可重跑 write receipt，尚未證明 `0x08691858` 的完整來源或任何文本語義。

工具只讀 ROM；輸出的 `work/afej-recon.json` 是本機偵察報告，不進 Git。它會記錄 GBA 標頭、校驗值、雜湊、標準 Shift-JIS 探針、ROM 內指標候選、BIOS 壓縮標頭候選及 4bpp 字形窗口的啟發式候選。候選不能單獨視為文本或字型證據，必須再以執行期畫面／VRAM 或可重現的字節交叉比對確認。

偵察完成後，遊戲專屬工具必須再提供：

1. 嚴格、可重跑的本機結構化原文／code-unit 表 `research/afej-decoded.jsonl`（目前為 opaque tokens；該檔案被忽略，不能提交）。
2. `work/` 中含原文的翻譯工作記錄。
3. 只含 `source_hash` 的 `translations/*.jsonl` ledger；只能由 `core/ledger/strip_translations.rb` 產生後提交。
4. 回插後重新抽取、BPS round-trip 與 mGBA 場景驗證；在此之前不得宣稱翻譯或可逆構建完成。

## 簡繁與術語

正式繁體目標是 `zh-TW`，不是未指定的 `zh-Hant`。初步臺灣社群慣用名保存在 `translations/glossary.zh-TW.tsv`；每個專名仍需在實際 ROM 語境中核對，來源分歧時保留分歧並標記，不自行創造音譯。

## 提交邊界

只可 stage 本目錄內的文件、工具、可公開研究筆記與不含原文的翻譯 ledger。不要使用 `git add -A`；ROM、`work/`、原文表、圖片、OCR 輸出與構建產物均留在本機。

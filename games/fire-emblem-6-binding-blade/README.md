# 《聖火降魔錄：封印之劍》日版（AFEJ）

本目錄只處理 GBA 日版《ファイアーエムブレム 封印の剣》（Fire Emblem: The Binding Blade）。原始 ROM 必須由貢獻者自行提供，僅放在被 Git 忽略的 `roms/`；本專案不保存 ROM、完整日文腳本、未授權字型或來源不明的大段原文。

## 目前狀態

截至 2026-08-16，已由使用者提供的本機日版 ZIP 唯讀解出一份 8 MiB ROM 到被忽略的 `roms/base/AFEJ.gba`，並完成 GBA 標頭、CRC32、SHA-1／SHA-256 與 `recon_afej.py` 核對。ROM 未加入 Git。

目前已由 AFEJ 執行期確認一條文字路徑：EWRAM 文字緩衝區會被字元消費者讀取，經兩位元組碼表查找後，glyph index 會寫入 EWRAM 渲染物件並進入 VRAM bitmap composer。完整劇情／支援／事件表、控制碼、glyph pool／tile stride／palette 對應與可逆回插仍未完成。

M1.5 已再確認一個有限 producer：ROM pointer table `0x080f635c[index 3087]` 取出 `0x080f2256`，經 copy／IWRAM worker 寫入 `0x02029404`，並在 renderer 實際觀察到 `0x01` marker 與 payload 後的 `0x00` 邊界。M1.6 已反組譯實際 loader entry `0x08013ad0`、IWRAM worker 的 ROM 初始化來源，並建立 `index 3080..3095` 的 16 筆 opaque-token corpus；16/16 decode→encode source bytes 相等，index 3087 的固定 buffer hash 也與獨立 runtime receipt 相等。source encoding、`0x01` 的換行／等待／結束語義及完整表格仍屬 provisional；沒有開始大批翻譯。

M1.7 已往上確認高階 caller：`0x08098afc` 以 selector 經 ROM table `0x08691738` 映射到 loader index，並在實際 `BL 0x08013ad0` callsite `0x08098b10` 觸發 index 3087。loader 的 copy-wrapper BL 真正起點是 `0x08013b02`；`0x08013b04` 是同一條 ARM7TDMI 雙半字 Thumb BL 的第二個 halfword，不能用來命名 caller 或解讀 LR。Start 可自然到達不同的顯示狀態，但 bounded 觀察沒有再次命中 `0x08013ad0` 或 `0x02029404` write-watchpoint，因此第二場景尚不能歸入 3342-entry table；`0x01` 仍是 opaque。

M1.8 已靜態枚舉 AFEJ 全 ROM 163 個合法、對齊的 ARM7TDMI 雙半字 Thumb BL direct callsites，分成 104 個 bounded prologue/return caller group。不同於 selector table 的最佳候選是 `0x080985d8`–`0x08098620` 內的 `0x080985ec`：函式先把參數 `r0` 存入 stack，再載回作為 loader index。自然 `KEYINPUT` 導航仍只重現 `0x08098b10`／index 3087；因此另以真實 Thumb loader stop 為 state seed，對 `0x080985ec` 做明確標記為 controlled 的 index 3086 probe，取得 `lr=0x080985f1`、`0x080f9394` → `0x080f2241`、EWRAM hash `beef794a…f9376e11`、terminator 31、`0x01` offset 12。第二 caller 的內容類別與 renderer 消費仍 unknown；`0x06014000` sink 本輪新 watchpoint 零命中，`0x01` 仍 opaque。

M1.9 已用三個 fresh mGBA／各自單一 GDB connection，僅透過 active-low `KEYINPUT` read-watchpoint 導航，完成三條 bounded natural route：`start,a`、`start,a,a,a`、`start,a,a,a,a,a,a,a,a,down,a,a,start,a`。三條都自然命中既有 selector `0x08098afc` → `0x08098b10` → index `3087`，沒有命中第二類 `0x080985ec` 或 `0x08098624`；每條都有 `0x08013ad0=1`、`0x08098b10=1`、第二 caller=0 的 hit-count、VRAM hash 與 display-register receipt。自然 consumer `0x08098c24` 實際讀取 `0x02029404`，`0x08098c78` 也命中控制分支；但本三條路徑均沒有命中 `0x08099424`、`0x080995b0`、實際 CPU `str r1,[r2]` 的 `0x080995a6` 或固定 sink watchpoint。這是精確 bounded negative，不把 M1.8 controlled probe 冒充自然 reachability；`0x01` 仍為 opaque，未建立 codepage 或語義分類。

M1.25 已把 consumer 控制結構與原始 leaf 序列 guard 固化為可重跑工具 `tools/analyze_m125_control_corpus.py`。對 bounded `index 3064..3095`，32/32 筆保留 table/source/output hash、marker offsets、長度與 provenance，並完成原始 decode→encode byte equality；此 guard 不允許任意新文字 encode、marker 改寫或 ROM 回插。static gate 只記錄 `0x08098c24` 的 byte read、`value <= 0x01` → `0x08098c78`、`value == 0x04` → `0x08098c80` 及 `0x08003e60` callsite，不替 marker 命名。

兩份 ignored M1.19 natural receipt 的 bounded consumer reads 都在 buffer offset `8` 實讀 opaque `0x01`，各自的 static read target 是 `0x08098c78`，獨立 branch hit count 為短 route `1`、長 route `2`；兩份 branch receipt 都沒有可配對的 source byte，且沒有 `0x00` 行為對照。因此 `0x01` 語義、scene/content category、Unicode 身分、翻譯 ledger、任意 encode 與回插仍未完成。

M1.26 已將 source/provenance census 擴成兩個不重疊的 16 筆窗口：`2672..2687`（含 natural generic caller `0x08009252` 的 2678／2679）與 `3080..3095`（含 selector caller `0x08098b10` 的 3087）。32/32 筆共用同一 strict tree worker、source-span 與原始 leaf round-trip；兩條 natural route 的 4 筆 loader receipt 其 source pointer 4/4 對上、output hash 3/4 對上，2679 mismatch 仍保留為未定原因的 negative。這只擴大格式／來源證據，不把兩個 caller family 或 route 名稱升格為內容類別。

M1.27 已將字型渲染後段固化為可重跑的 static contract：`0x080995b0` 對 `0x08099580` 呼叫四次，plane offset 為 `0x00/0x40/0x80/0xc0`；kernel 以 nibble mask `0x0f << ((r2 & 7) * 4)` 清除並合併 packed word，最後在 `0x080995a6` 寫回動態 destination。這是位元／plane data-flow 證據，不是完整 font pool、palette、Unicode 或字形身分；fresh writer hash pairing 若未取得仍維持 negative，沒有開始回插。

M1.28 已把兩份 ignored M1.19 natural receipt 的 map lookup 與 glyph-field write 做 deterministic join：每條 route 各 8/8 配對，map entry pointer 都符合 `0x08691644 + map_index*2`，glyph index 與 map index 8/8 相等，glyph field offset 固定為 `0x4a`。這只確認 bounded text buffer→map→glyph object 的索引資料流；兩份 receipt 的 renderer/writer 都是 0，因此 font-source／VRAM byte pairing、Unicode identity 與 scene category 仍 unknown。

M1.29 已將 composer 的 map-index→font-source address formula 以 strict AFEJ static check 固化：source base `0x02000000`、destination base `0x06010000`、config address `0x02002800`、offset mask `0x3ff` 均重新核對；121 個 map index 都產生 bounded formula row，兩份自然 receipt 的 16 個 lookup index 都可 resolve。這是 computed address candidate，不是 font pool bytes／Unicode identity；runtime source address 與 writer pairing 仍未取得。

M1.30 已完成 address-only source layout census：121 個 formula address 無碰撞；相鄰 map index 的 computed offset 有 `0x40` 連續 stride 113 次、`0x440` bank gap 7 次，形成 8 個數學 formula bank（前 7 個各 16 slots、最後 9 slots），不替它們命名為已確認的字型區。兩個不重疊 16-record windows（`2672..2687`、`3080..3095`）共 32/32 保持 worker decode→encode byte-identical，32/32 嚴格通過 Shift-JIS candidate decode；這是 code-unit readiness gate，不是 Unicode identity 或翻譯 ready。兩份 natural receipt 的 16 個 lookup 都可 join formula bank/slot，source bytes、font pool bytes、renderer/writer pairing 仍未取得。

M1.31 已由 `0x08098aee` → `0x08099404` 建立 source initializer provenance：initializer 以 `0x0837f478` ROM asset 與 `0x02000000` EWRAM destination 呼叫 `0x08013ca4`；source header class `0x10`、expanded size `0x2800`、dispatcher table entry `0x0809dcf5` → `SVC #0x11` 的 bounded LZ77-WRAM path 可重跑，compressed span consumed `0x1a53` 並以 1 byte alignment padding 接到 `0x08380ecc`。expanded source payload 只保存 hash。這也收斂 M1.29/M1.30 的過寬邊界：在 121 個數學 formula inputs 中，只有 0..79 的 plane word reads 落在 expanded window，80..120 是明確 out-of-window negative，不再視為 font slots；兩份 natural receipt 的 16 個 lookup 仍全在 bounds 內。font bytes 的同 run runtime read、font identity、Unicode 與回插仍未宣稱。

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

要重跑 M1.25 的 bounded control corpus（runtime receipt 只從 ignored `/private/tmp` 讀取）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m125_control_corpus.py \
  roms/base/AFEJ.gba --start 3064 --count 32 \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m125-control-corpus.json
```

這份報告只保存 marker offsets/counts、hash、loader provenance、consumer branch topology 與 bounded runtime hit/read 摘要，不保存 source bytes、code-unit bytes、完整日文或 raw RAM。`0x01` 的 branch target 是結構性收據，不是 newline／wait／end 名稱；`encode_guard.scope=original_decoded_leaf_sequence_only`，未宣稱可安全回插。

要重跑 M1.26 的跨 caller source/provenance census：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m126_provenance.py \
  roms/base/AFEJ.gba --range 2672:16 --range 3080:16 \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m126-provenance.json
```

`scene_or_content_category` 固定為 `unknown`；工具只 join table/source/output hash、caller LR/callsite 與 bounded route metadata，不輸出完整原文、code-unit bytes 或 Unicode。

要重跑 M1.27 的字型 plane/nibble static contract：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m127_font_contract.py \
  roms/base/AFEJ.gba \
  --output /private/tmp/afej-m127-font-contract.json
```

工具會先嚴格核對 AFEJ game code／SHA-256，再輸出 instruction hash、plane offsets、nibble data-flow 與 writer boundary；不輸出 bitmap bytes、RAM dump 或完整原文。

要重跑 M1.28 的 map-index／glyph-field deterministic join：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m128_map_glyph_pairing.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m128-map-glyph-pairing.json
```

輸出只含 code-unit SHA-256、map/glyph index、ROM map entry pointer、glyph object field offset 與 renderer/writer hit counts；不含兩位元組 code-unit、完整日文、bitmap 或 raw RAM。

要重跑 M1.29 的 map-index／font-source address formula census：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m129_font_source_formula.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m129-font-source-formula.json
```

輸出只含公式、literal provenance、map index、computed address 與 code-unit hash；不把 computed source address 當成已讀取的 font bytes，也不宣稱可回插。

要重跑 M1.30 的 source-layout／code-unit readiness census：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m130_source_layout.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m130-source-layout.json
```

預設只讀兩個不重疊的 bounded windows `2672:16` 與 `3080:16`；輸出含 formula bank／stride／collision count、record hash sequence、round-trip／marker count 與 natural lookup join，不輸出 source bytes、完整日文、Unicode 或 bitmap。

要重跑 M1.31 的 font-source initializer／LZ77 provenance：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m131_font_initializer.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --runtime-report /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m131-font-initializer.json
```

輸出只含 initializer／dispatcher instruction receipts、壓縮 span／expanded hash、formula bounds 與 natural lookup count；不輸出 compressed/expanded payload、font bytes、bitmap 或 Unicode。特別注意：formula input `80..120` 是 expanded source window 之外的 negative，不能當作已定位 glyph pool。

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

M1.16 沿同一個 static callsite 往下追 `0x08003c54`：ROM 內只有一個合法 direct BL caller `0x08003a0e`，helper function boundary 是 `0x08003c54–0x08003c7e`。四個 literal load 都指向 `0x08003c74`，其 literal value 是 EWRAM global address `0x020258c8`；指令資料流是 `[0x020258c8] → cursor`、`[cursor] → return value`、再將 `cursor + 4` 寫回同一 global，最後回傳暫存的 pointed value。這是 static provenance，不把它命名為 allocator 或文本物件。

fresh mGBA／單一 GDB connection 的同一路徑取得 56 組 `0x08003c54` entry／`0x08003c7e` return receipts（entry/return hit count 各 56）。每組 entry 的 `LR=0x08003a13` 都回推到 `0x08003a0e`；首組 `global_before=0x020257c4`、`[cursor]=0x02023cc4`，return `r0=0x02023cc4` 且 `global_after=0x020257c8`，56/56 組均滿足相同關係。該 bounded route 也重現既有 selector/generic loader chain；但沒有用 allocator 收據替代文本 consumer／renderer 證據，完整 JSON 只留 `/private/tmp`，不提交 raw EWRAM。

M1.16 的可重跑命令（先以自己的 mGBA GDB port 啟動 AFEJ）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m112_dispatch.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25042 \
  --route-name m116-natural-generic-allocator \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a \
  --output /private/tmp/afej-m116-natural-generic-allocator-schema.json
```

M1.17 對實際 text consumer `0x08098c00–0x08098c8c` 做 static branch gate：`0x08098c24: ldrb r0,[r6]` 後，signed-byte branch `0x08098c28 → 0x08098c3c`、`value <= 1` branch `0x08098c2c → 0x08098c78`、`value != 4` branch `0x08098c30 → 0x08098c3c`，而 `0x08098c7a` 呼叫 `0x08003e60`。工具把這些只記為 opaque branch topology，不為 `0x00`／`0x01` 建立語義名稱。

先前成功完成的 natural `title → Start → A` receipt（`/private/tmp/afej-m117-natural-selector-consumer.json`）在 `0x08098c24` 讀到 opaque `0x01`、buffer pointer `0x0202940c`／offset `8`，隨後取得 `0x08098c78` branch receipt；同一路徑 selector／loader hit count 是 `1/1`，第二 caller 是 `0`，只保存 hash、位址與 offset。新增的 compare-instruction receipt 會另外記錄 branch compare 當下的 `r0`，但本輪三次 fresh retry 都在 mGBA stale packet 的 bounded point/register transport 層失敗（`0e16`、無完整 `g` response、`P1` 無 `OK`），沒有把失敗重試冒充 positive runtime 證據。

M1.17 的 static／natural consumer 命令（先啟動自己的 mGBA；完整 JSON 留在 ignored `/private/tmp`）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m19_natural.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25047 \
  --route-name m117-natural-selector-compare \
  --sequence start,a --max-records 2 --max-consumer-reads 32 \
  --no-display --output /private/tmp/afej-m117-natural-selector-compare.json \
  --static-output /private/tmp/afej-m117-static-compare.json
```

M1.18 將相同 static map 與 compare breakpoints 接到 `trace_m112_dispatch.py` 的 core GDB client。`start,a` short route 的 loader return 是 `1`、compare／consumer hit 是 `0`；長序列 `start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a` 在較長 final window 得到 loader return `3`，compare／consumer hit 仍是 `0`。這是 bounded route/instrumentation negative，不能覆寫 M1.17 由 EWRAM read-watch 觸發的既有 `0x01` branch receipt，也不能替 `0x01` 命名語義。

可重跑 stable-client capture（先啟動自己的 mGBA）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m112_dispatch.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25049 \
  --route-name m118-natural-long-consumer-compare \
  --sequence start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a \
  --initial-seconds 2 --step-seconds 0.8 --final-seconds 4 \
  --output /private/tmp/afej-m118-natural-long-consumer-compare.json
```

M1.19 新增 `tools/trace_m19_glyph_sink.py`，只在按鍵注入期間安裝 `KEYINPUT` read-watchpoint；收滿 bounded glyph-field cohort 後移除 map／consumer detail breakpoints，讓自然 render worker 繼續執行。static gate 固定 map lookup `0x080992dc`／map base `0x08691644`、glyph-field writer `0x08098c62`（object layout offset `0x4a`）、真正的 composer `BL` `0x08099462 → 0x080995b0`、kernel `0x08099580` 與 CPU writer `0x080995a6: str r1,[r2]`。這些 label 只描述資料流，不命名 Unicode、font pool 或控制碼。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m19_glyph_sink.py \
  roms/base/AFEJ.gba --port 23901 --source-port 25056 \
  --route-name m119-natural-start-a-detail-released --sequence start,a \
  --initial-seconds 2 --step-seconds 1 --final-seconds 4 \
  --event-timeout 1.2 --max-records 8 \
  --output /private/tmp/afej-m119-natural-start-a-detail-released.json
```

本次 fresh `start,a` receipt 保存 loader `1`、map lookup `8`、glyph-field write `8`；長 natural route `start,a,a,a,a,a,a,a,a,down,a,a,start,a,b,b,left,right,up,down,a` 保存 loader `3`，但 `0x08098f68`／composer／kernel／writer 均為 0。這是 bounded scene/instrumentation negative；M0/M1 既有 `0x08099424`／`0x080995b0`／`0x06014000` 正向 baseline 另存，不能與本次 0-hit 合併成同一份 receipt。完整 JSON 僅留 ignored `/private/tmp`，不提交 ROM、RAM 或完整原文。

M1.20 的 hash-only map/font-pool census 可重跑如下；`--runtime-report` 只讀 ignored runtime receipt，不輸出 raw source／RAM：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m120_font_pool.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m117-natural-selector-consumer.json \
  --output /private/tmp/afej-m120-font-pool-census.json
```

目前 census 固定 ROM map `0x08691644` 的 121 筆 bounded pair、`0x08691736` 的 `0x0000` terminator、wrapper `0x08099314` 的 literal `0x086916e5` 與 indexed-byte window；runtime 部分只統計 glyph source／VRAM address、hash receipt count、group base stride 與 outlier，不替 indexed bytes 命名寬度、字形或 Unicode。既有 M1.17 report 的 21 composer／63 renderer entries 只支持 `0x020020c0`／`0x06014000` 的地址與 `0x40` 常見 transition；source/writer hash 缺失時仍標為 provisional。

M1.21 的 composer literal／address formula 與 ignored runtime receipt census 可重跑如下；工具不輸出 literal 對應的 raw ROM bytes，也不把舊 receipt 當作 fresh writer proof：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m121_font_source.py \
  roms/base/AFEJ.gba \
  --runtime-report /private/tmp/afej-m117-natural-selector-consumer.json \
  --output /private/tmp/afej-m121-font-source.json
```

static 結果確認兩個 composer 變體的 source base literal 是 `0x02000000`、destination base literal 是 `0x06010000`，另有 `0x02002800` config 與 `0x000003ff` mask；`0x020020c0` 與 `0x06014000` 只作 computed-address candidate。既有 ignored report 的 63 筆 renderer address pair 中兩者均觀察到，但 source hash／writer receipt 都是 `0`，所以不能宣稱同一-run byte equality。這次 fresh mGBA writer refresh 沒有取得可用 23901 listener，該 transport 結果不作遊戲語義證據。

M1.22 的 bounded codepage candidate 可重跑如下；第二、三個輸入是 ignored research/runtime，不會把完整日文或 raw bytes 寫入輸出：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m122_codepage.py \
  roms/base/AFEJ.gba research/afej-decoded.jsonl \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --output /private/tmp/afej-m122-codepage.json
```

目前結果是 121/121 map pairs 可 strict Shift-JIS 解碼；natural `start,a` receipt 的 8 筆 map lookup 與 8 筆 glyph-field 都有 map pair／glyph index equality，前 4 筆 code-unit hash 與 index 3087 corpus prefix 相符。這只建立 `shift_jis_candidate_with_runtime_map_correspondence`，不確認完整 Unicode identity、場景／內容分類或翻譯 readiness；M1.6 corpus 與所有原文仍維持 ignored source/work 邊界。

M1.23 的 32 筆 bounded strict corpus 與 natural receipt 對照可重跑如下；輸出只含 hash、長度、marker、script-count 與 caller/display provenance：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/extract_m123_bounded_corpus.py \
  roms/base/AFEJ.gba --start 3064 --count 32 \
  --runtime-report /private/tmp/afej-m119-natural-start-a-detail-released.json \
  --output /private/tmp/afej-m123-corpus.json
```

目前 32/32 records 皆 decode→encode byte-identical、相鄰 source span 相等且通過 Shift-JIS candidate decode；index 3087 的 static output hash 與 natural loader buffer hash 相等。這是 bounded extractor/receipt 證據，不是劇情、支援、事件或選單分類；完整 `tokens`／原文仍只留 ignored research/work。

M1.24 的兩條 natural route scene witness 可重跑如下；工具只 join caller/index/source/hash/display 摘要，不從 route 名稱猜 title、menu 或章節：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_m124_scene_witness.py \
  roms/base/AFEJ.gba \
  /private/tmp/afej-m119-natural-start-a-detail-released.json \
  /private/tmp/afej-m119-natural-long-menu.json \
  --output /private/tmp/afej-m124-scene-witness.json
```

短 route 只有 `0x08098b10`／3087；長 route 另到達 `0x08009252`／2678、2679，兩者均在同一 `[0,3342)` pointer domain，final display receipt hash 分別為 `0336199589aac65710b0ccc58897470bb9ce39787993b16be981b46d9c6234ff` 與 `22258df5305bbdb7970e4cdf62260e4e012f0291f046e375605028685cd7b4bc`。4 筆 loader receipt 中 3 筆 static/runtime buffer hash 相等；2679 的 full-buffer mismatch 保留為 negative，工具不猜是 tail 或 capture sequencing。scene/category、`0x01` 與 Unicode identity 仍 unknown/provisional。

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

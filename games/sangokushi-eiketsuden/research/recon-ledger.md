# 《三國志英傑伝》唯讀偵察帳

## 基本邊界

- 遊戲 slug：`sangokushi-eiketsuden`
- 目標版本：日版 GBA；產品候選 `B3EJ`；本 session 不處理《三國志孔明伝》
- 本帳只記錄工程偵察和證據狀態，不保存 ROM、完整原始腳本、字型 dump、OCR 圖片或大段外部攻略原文。
- 建立日期：2026-08-16（Asia/Taipei）
- `confirmed-static` 只表示可由本機 ROM 與可重跑工具重現；`confirmed-runtime` 只表示執行期讀值／事件已觀察，兩者都不等於已完成 decoder 或翻譯。

## ROM receipt

| 欄位 | 結果 | 證據／限制 |
|---|---|---|
| 來源 archive | 委派提供的本機 ZIP；單一 entry | ZIP 只讀核對；檔名含 legacy CJK ZIP filename bytes，未把 archive 加入 Git |
| local ROM | `roms/base/B3EJ_JP_candidate.gba` | `roms/` 已忽略；ROM 不進 Git |
| decompressed size | `4194304` bytes（4 MiB） | ZIP entry 與檔案大小一致 |
| ZIP entry CRC32 | `a4a1c956` | 只作 archive 解壓完整性核對 |
| title | `EIKETSUDEN` | header `0xA0–0xAB` |
| header game code | `B3EJ` | header `0xAC–0xAF`；與產品候選分開記錄後相符 |
| maker code | `C8` | header `0xB0–0xB1` |
| software version | `0` | header `0xBC` |
| header complement | stored `0xe1`; calculated `0x13`; **mismatch** | 依 GBA header bytes `0xA0–0xBC` 的標準公式計算；原 ROM 未修補 |
| CRC32 | `a4a1c956` | 本機完整 ROM |
| MD5 | `76cccc133899422854687e672f335cbd` | 本機完整 ROM |
| SHA-1 | `32b5eeb82b0ffa14adc54223fb9e423efe8a1aa4` | 本機完整 ROM |
| SHA-256 | `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0` | 本機完整 ROM |

## 證據矩陣

| 項目 | 狀態 | 已有證據 | 尚未證實／下一個安全邊界 |
|---|---|---|---|
| 公開產品候選 | `confirmed-public` | 公開資料列出 `AGB-P-B3EJ`；來源見 `term-sources.md` | 公開資料不能替代本機 ROM hash |
| ROM 身分 | `confirmed-static` | header `EIKETSUDEN`／`B3EJ`／`C8`／revision `0`，大小與 hash 已記錄 | header complement 異常要保留，不能當作 clean dump 證明 |
| codepage | `confirmed-static` | 多個集中區可直接以標準 Shift-JIS 解出日文；probe 命中 `策略`、`劉備`、`援軍`、選單詞等 | 尚未把每一池與遊戲畫面／呼叫點逐字串對應 |
| 文本候選區 | `confirmed-static / provisional-map` | `0x075a80–0x077100`、`0x078528–0x0786fc`、`0x07880c–0x078848`、`0x079764–0x0797e4` 有可讀 Shift-JIS／系統或事件候選 | 尚未區分完整劇情、武將、地名、官職、策略和戰役 event 的所有池 |
| 四池 decoder | `confirmed-static / source-local` | `tools/extract_text_pools.py` 對 A `183/183`、B `44/44`、C `4/4`、D `28/28` 做 bounded absolute-pointer、NUL、Shift-JIS 驗證；A 有 `177` 筆 LF，四池均無 opaque control byte；完整原文只寫 ignored decoded JSONL | pool A/C/D 的自然畫面／劇情語意與完整 runtime glyph identity 尚未逐池核對；D 有 6 筆空字串，保留為資料而不臆測 |
| 終止與排版 | `confirmed-static / provisional` | 多個候選字串以 `0x00` 結束，觀察到 `0x0a` LF、全形空白 `81 40` | 最大行寬、游標語意、續行規則尚未驗證 |
| 控制／格式 | `provisional-static` | 觀察到 `ESC C6 %s` 候選序列與 `%s`／`%d`／`%u`／`%%` 參數 | `ESC C6` 是否為遊戲控制碼、參數消費規則和插入限制尚未證實 |
| pointer width／形態 | `confirmed-static` | 32-bit little-endian absolute GBA ROM pointers；target = `0x08000000 + file offset` 的表格可重跑 | 不是所有 aligned pointer 都是文本；事件／map struct 仍需 code-flow 核對 |
| pointer table A | `confirmed-static / text-candidate` | file `0x0cbc54`, 183 entries；149 unique targets；target `0x075a80–0x077100` | 表尾後的其他 entries 與資料結構尚未完整命名 |
| pointer table B | `confirmed-static / text-candidate` | file `0x0d1ffc`, 44 entries；26 unique targets；target `0x078528–0x0786fc` | 需以執行期選單／戰鬥畫面核對 |
| pointer table C | `confirmed-static / text-candidate` | file `0x0d20d8`, 4 entries；4 unique targets；target `0x07880c–0x078848` | 需核對其所屬畫面／事件 |
| pointer table D | `confirmed-static / text-candidate` | file `0x0d4d00`, 28 entries；16 unique targets；target `0x079764–0x0797e4` | 鄰接欄位含非 pointer 小資料，不能整段當純文字表 |
| runtime execution | `confirmed-runtime / bounded / title-screen` | 以共用 `core/gba/capture_runtime.py` 在本 session 獨立 mGBA/GDB port `39123` 完成標準 capture；初始／繼續停止狀態均可讀，ROM、IWRAM、VRAM、OAM 和 palette 均非空 | 尚未完成穩定畫面導航、文字呼叫 breakpoint 或 glyph identity 核對；本 capture 尚未把靜態 Shift-JIS 池連到特定呼叫點 |
| display mode／BG 配置 | `confirmed-runtime` | capture 的 `DISPCNT=0x1e40`（Mode 0、OBJ 1D）；`BG0CNT=0x1400`、`BG1CNT=0x1501`、`BG2CNT=0x1602`、`BG3CNT=0x1703`，分別使用 screenbase `0xa000`、`0xa800`、`0xb000`、`0xb800` | 這是標題畫面當下配置；尚未證明劇情／戰役畫面沿用相同 screenbase 或 tile 組織 |
| rendered title screen | `confirmed-runtime / visual-evidence` | 用共用 `render_vram.py` 依上述 BG 設定產生 ignored PPM/PNG：BG0 可見英文開始提示、BG1 可見版權列、BG2 可見日文標題圖樣、BG3 為紅黑圓形裝飾；共用 `render_oam.py` 在 OAM 1D 模式下顯示 0 個可見 sprite | 可證明 GBA tile／tilemap 渲染路徑與目前畫面分層，不證明 BG2 圖樣或任何 ROM 區段就是可解碼劇情文字／字型 |
| VRAM／DMA | `confirmed-runtime / bounded` | 先前與本次 capture 均觀察到 DMA／資料搬移及非空 VRAM；已知例包含 `0x08079a08 -> 0x03004ee0`、`0x020013d8 -> 0x06000000` 類事件 | 這只能證明執行期圖形資料活動，不證明某段就是字型或文字 tile |
| M2 selected short record | `confirmed-static / controlled-runtime` | table B（`0x0D1FFC`）entry `0` 指向 file `0x078528`；payload 14 bytes、SHA-256 `c7ac47044e9576475f854841981b18ae20eca25ad41df403164ee6307b1aecca`；controlled wrapper event 標記 `record_pointer_is_B0=true` | natural consumer／選單畫面仍未觀察；controlled pointer hit 不代表自然 reachability |
| M2 pointer／record → writer | `confirmed-static / controlled-runtime; natural-not-observed` | M2.2 static chain 已從 `0x0800d3fc` output buffer 接到 `0x0800cad8` writer、`0x08008d18` SJIS renderer、`0x080650a4` lookup、`0x080650dc` glyph expand、`0x080656d4` 128-byte VRAM copy 和 `0x08008914` tilemap writer；M2.3 controlled consumer 取得 cache／VRAM／tilemap hash receipts | natural 32-event slice 沒有 consumer／index hit；不能把 controlled chain 寫成自然畫面 evidence |
| M2.1 table B 邊界 | `confirmed-static` | file `0x0d1ffc` 到 `0x0d20ac` 為 44 個連續 GBA pointer；下一個 word 為零，table C 從 `0x0d20d8` 開始；record target 有 26 個唯一落點 | 呼叫端只證實 index `& 0x7f`；本地未證實 `<44` bound，不能把 dispatch 的 `cmp #0x22` 當成 table B bound |
| M2.1 static consumer chain | `confirmed-static / Thumb` | `0x080262f8` literal 取 table base；`0x080262fa–0x08026306` mask／scale／load record pointer；`BL 0x0800d8f0` 再 `BL 0x0800d3fc` | 已到 byte reader／formatter；沒有 glyph writer 或 tile destination 證據 |
| M2.1 table B record 結構 | `confirmed-static` | 44/44 為 NUL 終止且可由標準 Shift-JIS 解碼；payload 長度為 14×16、16×22、18×6；`0x0a`、格式參數和其他 `<0x20` opaque 控制 byte 皆為 0 | 結構結論只適用 table B；未知控制 byte 仍須保留 opaque，不由靜態解碼推論 glyph identity |
| M2.1 runtime retry | `pending / bounded-negative` | 兩次新 process／獨立 port、無 bind shim；第二次可讀 GDB I/O／VRAM 並命中 16 次 KEYINPUT watchpoint | 未命中 table pointer、record 或 `0x0800d8f0` wrapper；沒有導航到 consumer 的 runtime evidence，本切片不再重試 |
| M2.2 output buffer／writer chain | `confirmed-static / controlled-runtime` | formatter `0x0800d3fc` 在 `sp+0x18` 建立 NUL-terminated output；`0x0806ed80` 是 `bx r2` veneer，literal 解析到 writer `0x0800cad8`；writer 的 SJIS path、renderer、lookup、glyph expand、cache、128-byte VRAM copy、tilemap callsite 均在有效 Thumb span 內，M2.3 controlled call 已逐段命中 | natural output path 仍未觀察；controlled evidence 只證明受控 consumer fixture |
| glyph addressing | `confirmed-static / confirmed-controlled-runtime` | codepage table file `0x024110c` 有 1834 entries；lookup index 保存於 `0x080650ec`，glyph expander 以 index×`0x20` 取 source，寫入 cache `0x02000000` 128 bytes；controlled receipts 顯示 cache hash 與 VRAM after hash 相同 | `0x08000214` 的 `r2` 是 byte count，已修正為 128-byte receipt；其他 code unit 的 Unicode identity 仍不可由 hash 單獨推論 |
| Unicode identity | `confirmed-static-for-three-sentinels / confirmed-controlled-U+90E8` | table B entry 0 的三個 strict Shift-JIS code `0x9594`／`0x82c9`／`0x97cd` 分別解為 U+90E8／U+306B／U+529B，並各自連到 codepage index 與兩組 static glyph chunk hash；M2.3 runtime 觀察 `0x9594`、index `1301`、U+90E8 | U+306B／U+529B 尚未在這個 32-hit controlled slice 內命中 runtime glyph；identity 與 addressing 仍分欄 |
| M2.3 upstream builder | `confirmed-static / global-bound-pending` | `0x08026510 → 0x0801929C`；`r6+0x02` 是 builder return count，`r6+0x1C` 是 `sp` output buffer；empty path return 44，normal path runtime table `0x02014E78` 以 `0xFF` 終止 | normal path 的所有 runtime table values 尚未取得；不能把 empty path 的 44 外推為全域 bound |
| M2.3 controlled index cohort | `confirmed-controlled / bounded` | 1/32 possible rows：r6 `0x0203F000`、event array `0x0203F100`、byte `0x00`、event-array index `0`、actual index `0`、local length `1`、caller LR `0x0800C735`；`0<44` | controlled fixture 是人工建立，不證明自然 event source 或所有 future events |
| M2.3 natural index cohort | `negative / not-observed` | natural 32-event KEYINPUT slice 沒有 consumer/index setup hit；`natural_reachability=not-observed` | 需要更可靠的自然選單／戰役導航，不能把一次 bounded no-hit 當作永久否證 |
| M2.3 runtime readiness | `confirmed-runtime / transport-separated` | 官方 mGBA 自有 process 精確指向 B3EJ ROM、native listener 2345 readiness 成功；高位 forward 24569 readiness 也可單獨核對，但 forward GDB connection closed，故採 direct client 結果 | headless 2346 與現成 23901 均屬其他 session，沒有終止或重用 |
| M2.4 natural path 1 | `negative / bounded-natural` | fresh process／port `39123`；`none:8,start:4,none:20`；32 KEYINPUT stops，PC `0x0805CF5E`；builder／consumer／pipeline 皆 0；VRAM before/after SHA-256 `57ac3f390f4e9d4549ccb2a377688ae96f1890b16a4ee3c266816454dd1b753f` | title/input-read loop 未跨過 state gate；不是全遊戲自然不可達證明 |
| M2.4 natural path 2 | `negative / bounded-natural` | fresh native process／port `2346`；`none:4,start:8,none:20`；32 KEYINPUT stops；builder／consumer／formatter／writer 皆 0；screen I/O 與 VRAM hash 維持 title baseline | natural cohort `0`；尚無 actual index 或 runtime table count receipt |
| M2.4 static caller/state gate | `confirmed-static / indirect-dispatch` | initializer `0x080264A4` stores consumer pointer at `r6+0x10`、builder count at `r6+0x02`、event buffer at `r6+0x1c`，calls `0x0801A738`; state loop checks `r4+0x14`、polls `0x0801A12C`、再 loads `[r4+0x10]` and calls `0x0806ED80: bx r2`；`r6+0x14` source is `0x08021A44` predicate over EWRAM table `0x0203544C` | table byte 的 exact menu／battle semantic、natural event byte provenance、index `<44` 仍 unknown |
| M2.4 normal count | `unknown / runtime-pending` | static builder source remains `[0x02014E78]` terminated by `0xFF`; harness now records bounded sentinel/count metadata only when builder is naturally entered | no natural builder hit；不能把 empty-path count 44 外推 |
| compression | `not-confirmed` | bounded signature scan 僅得到 noisy counts：LZ77 `10744`、Huffman `6692`、RLE `4704`、Diff `4966` | 沒有把任何 signature 當成文本壓縮；需由 code／runtime 呼叫證實 |
| 可逆回插 | `record-level-no-op-only` | `verify_table_b_roundtrip.py` 對 table B 44/44 decode→Shift-JIS encode byte-identical、hash-identical、control-invariant；aggregate record hash `e08935e581f822010e5f9f7ba14db556abfd80c25162048019d88f60d2b29af5` | 只證明 record-level no-op；尚未證明 table relocation、ROM encoder、字庫覆蓋、patch 或完整抽出→回插 round trip |
| 翻譯 ledger | `ready / empty` | glossary 已有 `zh-TW` 候選；沒有 source table 或 translation record | decoder 完成前不建立翻譯批次，不猜 string ID |

## 可重現命令

以下命令只讀取 ignored ROM，輸出可審核的 metadata／偏移報告到 `/tmp`；不把原文窗口保存到 repo：

```text
PYTHONPYCACHEPREFIX=/tmp/sangokushi-pycache \
  python3 -m unittest \
  games/sangokushi-eiketsuden/tools/test_inspect_rom.py \
  games/sangokushi-eiketsuden/tools/test_scan_text_pointers.py

python3 games/sangokushi-eiketsuden/tools/inspect_rom.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  > /tmp/sangokushi-inspect.json

python3 games/sangokushi-eiketsuden/tools/scan_text_pointers.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  > /tmp/sangokushi-pointers.json
```

`inspect_rom.py` 的 bounded probe 只報告偏移與計數；`scan_text_pointers.py` 只報告 table／target 範圍。兩者都不輸出完整日文腳本。

## 共用 runtime capture（2026-08-16）

本次使用 Project Atlantis 共用 GBA 工具，不重寫遊戲專用 GDB client 或 renderer。原始 dump、rendered PPM/PNG 和暫存 mGBA build 均留在 ignored／暫存路徑，未納入本帳：

```text
PYTHONDONTWRITEBYTECODE=1 python3 core/gba/capture_runtime.py \
  --port 39123 --run-seconds 1 \
  --dump-dir games/sangokushi-eiketsuden/work/runtime \
  --output games/sangokushi-eiketsuden/work/runtime/summary.json
```

capture summary 的可審核讀值為：`DISPCNT=0x1e40`、`BG0CNT=0x1400`、`BG1CNT=0x1501`、`BG2CNT=0x1602`、`BG3CNT=0x1703`、`KEYINPUT=0x03ff`；EWRAM head、IWRAM、palette、VRAM 和 OAM dump 都有非零內容。以 `render_vram.py` 依四個 screenbase 輸出後，BG0–BG3 的畫面內容與上述 title-screen 分層相符；`render_oam.py --mapping 1d` 沒有可見 sprite。這次結果將 runtime 狀態從「可執行 sanity check」提升為「標題畫面 BG／tilemap 已觀察」，但仍保持字串池、字型 glyph 和回插路徑未證實。

## M2 bounded trace（2026-08-16）

本切片選定 table B entry 0（file pointer table `0x0D1FFC`、target `0x078528`）作為
早期戰役短 record 候選，完整邊界、payload hash、工具命令與分類見
[`research/m2-runtime-trace-20260816.md`](m2-runtime-trace-20260816.md)。新增的
`tools/trace_m2_runtime.py` 只引用共用 `core/gba/gdbstub_client.py`，不保存或輸出
原始文本；必要的視覺核對仍應使用共用 `core/gba/render_vram.py`。

本次已界定但未完成的 runtime slice：

- **confirmed**：B[0] 的 static pointer／payload hash 可重跑；既有 title baseline
  與 BG renderer evidence 不變；所有本 session mGBA 子進程已清理。
- **provisional**：B[0] 屬於 menu／battle effect pool，Shift-JIS byte-level 解讀
  有效；glyph addressing 只有 title-only evidence，Unicode identity 尚未對應到
  runtime glyph。
- **negative**：headless port `39123`、SDL 獨立 port `24388`、Qt 獨立 port
  `24387` 均未提供可用的本 session GDB runtime；沒有 KEYINPUT 導航後的 pointer
  read、record read、writer PC 或 VRAM delta。因此不能宣稱 source pointer／record
  已連到 runtime glyph/tile writer，也不開始翻譯批次。

## M2.1 static consumer chain（2026-08-16）

本切片改以 table B 為 static consumer chain 錨點，並以
`tools/analyze_table_b_chain.py`、`tools/table_b_common.py` 和
`tools/extract_table_b.py` 重跑。分析器只輸出 metadata；extractor 的 44 行原文
record 只寫到 ignored `research/sangokushi-eiketsuden-decoded.jsonl`，不進 Git。

- **confirmed**：table B file range `[0x0d1ffc, 0x0d20ac)` 為 44 個 32-bit little-endian
  GBA pointers；其後的零 word 與 table C base `0x0d20d8` 提供邊界交叉證據。record
  pool 有 26 個唯一落點，全部 44 筆均 NUL 終止並可作標準 Shift-JIS byte-level
  解碼。此池沒有 LF、`%s`／`%d`／`%u`／`%%` 或其他 `<0x20` opaque control byte。
- **confirmed**：有效 Thumb consumer function 位於 `0x08026054` 的 dispatch 內；
  `0x080262f8` 的 literal slot `0x08026350` 解析為 table base `0x080d1ffc`。
  `0x080262fa–0x08026306` 讀取 event-derived index、套用 `&0x7f`、乘四、加 table
  base、載入 record pointer，接著 `BL 0x0800d8f0`，wrapper 再呼叫
  `0x0800d3fc`。反組譯 span、literal pool、branch target 與下一個 function
  prologue 均由 ROM-independent tests／analyzer 驗證，沒有把 table data 當作 code。
- **provisional**：`0x0800d3fc` 的 byte reader／formatter 會讀取 record bytes 並
  分支處理 NUL／`%`；其後呼叫 `0x0806ed80`，但這個切片沒有證明它是 glyph writer。
  table B caller 的 `<44` index bound 也未找到；`cmp r4,#0x22` 是 dispatch jump
  table 的 bound，不是 table B entry count。
- **negative / pending**：兩次乾淨新 mGBA process／獨立 port 重試中，第二次確認
  transport、I/O／VRAM read 與 KEYINPUT watchpoint 可用，但只觀察到 16 次按鍵讀取，
  沒有 pointer／record read 或 wrapper breakpoint。故 runtime glyph/tile writer、
  glyph addressing 和 Unicode identity 仍未確認；不建立翻譯 batch。

當時的 next static edge 是檢查 `0x0800d3fc` 對 `0x0806ed80` 的 consumer／writer
語意；該 edge 已在 M2.2 完成，runtime 與回插邊界仍另行分層。

## M2.2 static pipeline（2026-08-16）

完整 source-safe offsets、function spans、sentinel hashes 和再現命令見
[`research/m2-2-static-pipeline-20260816.md`](m2-2-static-pipeline-20260816.md)。本
帳只保留可審核 metadata，不保存 record 原文或 glyph dump。

- **confirmed-static**：formatter `0x0800d3fc` 的 stack output `sp+0x18` 經
  `0x0806ed80: bx r2` veneer 解析至 writer `0x0800cad8`。writer 的 SJIS path
  `0x0800cb62` 呼叫 renderer `0x08008d18`，再呼叫 `0x080650a4` codepage lookup、
  `0x080650dc` glyph expand、`0x080656d4` VRAM copy 和 `0x08008914` tilemap writer。
- **confirmed-static**：codepage table file `0x024110c` 有 1834 entries；lookup
  index 在 `0x080650ec` 保存，glyph source 以 `base + index*0x20` 定址，cache 為
  `0x02000000`／128 bytes。三個 strict SJIS sentinel U+90E8、U+306B、U+529B
  各自有 codepage index 與兩組 static glyph chunk hash；Unicode identity 與
  glyph addressing 分開保存。
- **confirmed-static / record-level only**：44/44 records decode→encode
  byte/hash identical、control invariant；aggregate hash 為
  `e08935e581f822010e5f9f7ba14db556abfd80c25162048019d88f60d2b29af5`。這不表示
  ROM encoder、relocation 或 patch 已成立。
- **confirmed-static / not-proven**：consumer 的 local bound 仍是 `u16(r6+0x02)`；
  `event_byte & 0x7f` 不能當 `<44`。harness 會在 consumer/index setup 記錄 r6 base、
  fields、actual index 和 caller LR，並標記 `runtime-observed-only; not-static-proof`。
- **negative / pending**：一次新的 bounded pipeline listener attempt 沒有產生可用
  report 或 accepted natural/controlled hit；因此 runtime reachability、runtime
  glyph/cache/VRAM identity、有效 index 實例和自然畫面連結仍 pending。受控 hijack
  若未成功，不把它寫成自然 reachability。

## M2.3 runtime gate（2026-08-16）

完整 static upstream、controlled fixture、runtime receipt 與 transport 分類見
[`research/m2-3-runtime-gate-20260816.md`](m2-3-runtime-gate-20260816.md)。本帳只
保存 hash／位址／計數，不保存 runtime dump 或原文。

- **confirmed-static**：`0x080264A4` 的 initializer 在 `0x08026510` 呼叫
  `0x0801929C` builder；builder return count 寫到 `r6+0x02`，`sp` output buffer
  寫到 `r6+0x1C`。empty path index `0..43`、count `44`；normal path 使用
  runtime table `0x02014E78` 與 `0xFF` sentinel，因此 global `<44` 仍未證明。
- **confirmed-controlled**：RAM-only fixture 以 dispatch case `20` 呼叫 consumer，
  `event_byte=0x00`、actual index `0`、event-array index `0`、local length `1`、
  caller LR `0x0800C735`；這筆 provenance 是
  `controlled-consumer-consumer-index-setup`，不代表自然 reachability。
- **confirmed-controlled**：B[0] `0x08078528` → wrapper `0x0800D8F0` → formatter
  `0x0800D3FC` → writer `0x0800CAD8`，再觀察到 3 組 codepage／glyph cache、128-byte
  VRAM copy 和 tilemap writer receipts。`0x9594`／index `1301` 的 Unicode identity
  是 U+90E8；cache 與對應 VRAM after hash 相同。
- **negative / natural-not-observed**：自然最多 32-event slice 沒有 consumer 或
  index setup hit，故 natural cohort 為 0。這是本次導航的 bounded negative，不是
  全遊戲不會觸發的否證。
- **negative / transport-only**：24567 shim 不適配 headless build；24569 forward
  listener readiness 成功但 GDB connection closed。官方 mGBA direct 2345 readiness
  與 GDB harness 成功，所有 process 在 finally 清理；沒有終止其他 session。

M2.3 的 runtime gate 只對 controlled fixture 局部成立；自然 index bound、normal
path event source、U+306B／U+529B runtime identity 與 encoder／回插仍 pending。
因此不建立翻譯 batch。

## M3 bounded batch 1／fixed-slot round-trip（2026-08-16）

完整欄位、命令和限制見 [`research/m3-batch1-roundtrip-20260816.md`](m3-batch1-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 B0–B5 的日文 source 或 work artifact。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| B0–B5 translation ledger | `confirmed-static / ai-review` | `translations/table-b-batch-1.jsonl` 有 6 筆 source-free rows；每筆有 string ID、source hash、`zh-TW` target、上下文、max width、控制碼清單和 `ai_review` 狀態；restore→strip 逐 byte 相同 | 不是完整劇情／戰役批次；尚未通過自然畫面與人工最終術語審核 |
| strict encoder／font coverage | `confirmed-static / bounded` | 6/6 目標通過 Shift-JIS、1834-entry codepage、兩組 glyph bank 的 0x20-byte slot；missing codepage entry `0`、原 fixed span fit `6/6` | 僅限 B0–B5；不能外推 Table B 其餘 records 或 pool A/C/D |
| fixed-slot Table B patch | `confirmed-static / bounded` | 44-entry pointer table unchanged；6 unique targets、changed bytes `42`；relocation disabled；selected re-extract `6/6`、fixed-slot `6/6`，unselected records byte-identical | 只證明選定 record/table layer，不是全 ROM relocation／encoder proof |
| BPS build/apply | `confirmed-static / bounded` | BPS `109` bytes；source CRC32 `a4a1c956`、target CRC32 `83398341`、patch CRC32 `e65c22d2`；BPS SHA-256 `9a9d5ed9af847dbdf9dcaa48785be76eb5a107d41f3928711faabf2d7c20726e`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存，不把 ROM 或 BPS 提交；全池重抽取仍未完成 |
| patched runtime QA | `pending / not-observed` | 尚未取得 patched B0–B5 的自然 menu／battle runtime receipt | M2.4 natural cohort 仍為 0；既有 M2.3 controlled receipt 不可冒充本批次自然 evidence |

此 bounded batch 使「固定槽位的局部 encoder／BPS／re-extract」成立，但不解除自然
event index `<44`、完整字型／版面、pool A/C/D 翻譯、全量回插或 mGBA QA 的缺口。

## 後續證據邊界

1. 用 ROM-independent tests 保持 identity／pointer summary 工具可重跑。
2. 若重新做 runtime，使用本 session 自己的 mGBA 進程與獨立 GDB port；只記錄寄存器、DMA、VRAM／IWRAM 範圍和可重現 breakpoint，不提交 build、probe 或 ROM。
3. 只有在同一候選字串能以 pointer／code-flow／畫面三者交叉確認後，才建立本機 ignored decoded source table。
4. 目前只有 record-level no-op；只有未修改內容可抽出、回插、再抽出逐 byte 一致，才將 reversible insertion 從 `record-level-no-op-only` 改為 confirmed。
5. 第一批翻譯仍必須通過 `core/ledger/restore_translations.rb`、`strip_translations.rb`、schema、安全檢查與術語來源審核。

## 尚未採用的假設

- 不假設沿用黃金太陽、光明之魂或其他 GBA 遊戲的字型、壓縮、指標、控制碼或回插格式。
- 不把公開攻略、英文／中文 patch 或 static Shift-JIS 命中當成正式逐句翻譯來源。
- 不因 header complement mismatch 自動修補 ROM，也不將它改寫成「clean」版本。
- 不把 `B3EJ` 產品代碼單獨當成 ROM 身分；本帳以 header、大小和 hash 一起核對。

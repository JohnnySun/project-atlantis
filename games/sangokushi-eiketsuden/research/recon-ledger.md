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
| 文本候選區 | `confirmed-static / provisional-map` | `0x075a80–0x077100`、`0x077328–0x077e68`、`0x078528–0x0786fc`、`0x07880c–0x078848`、`0x079764–0x0797e4` 有可讀 Shift-JIS／系統或事件候選 | 尚未區分完整劇情、武將、地名、官職、策略和戰役 event 的所有池 |
| 四池 decoder | `confirmed-static / source-local` | `tools/extract_text_pools.py` 預設對 A `183/183`、B `44/44`、C `4/4`、D `28/28` 做 bounded absolute-pointer、NUL、Shift-JIS 驗證；A 有 `177` 筆 LF，四池均無 opaque control byte；完整原文只寫 ignored decoded JSONL | pool A/C/D 的自然畫面／劇情語意與完整 runtime glyph identity 尚未逐池核對；D 有 6 筆空字串，保留為資料而不臆測 |
| story-event pool E | `confirmed-static / static-consumer-confirmed; known-screen-cross provisional` | `0x0cdb64/33`、33 unique targets `0x077328–0x077e68`、33/33 strict Shift-JIS、32/33 LF、0 opaque controls；literal／caller chain `0x080cdb64 → 0x08011904 → 0x080118c8 → 0x0800cad8`；公開攻略的夷陵／結局分支與 E hash-only 分組相符 | natural ending／event reachability、E formatter→cache→VRAM receipt 和完整語意仍未取得；E 不是四池 custom-glyph non-use cohort |
| known-screen／codepage／layout cross | `provisional-known-screen-cross / confirmed-static-and-controlled subedges` | E:000–E:032 的 source-free ledger、LF／control／fixed-slot／re-extract／BPS metadata；common `0x080650a4` lookup → `0x080650dc` expander；controlled B[0] `U+90E8`、cache／VRAM／tilemap receipt；公開夷陵／生死流程作 bounded flow cross | E natural formatter→cache→VRAM、runtime glyph pool location and complete pixel layout remain pending；Unicode identity stays separate from addressing |
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
| M2.5 stable-title I/O timing | `confirmed-runtime / bounded` | fresh B3EJ process、single GDB connection 的 10 個一秒窗口：`DISPCNT` 於 1–4s=`0x0140`、5–6s=`0x0440`、7–8s=`0x0240`，9–10s 穩定 `0x1E40`；stable BG0–BG3=`0x1400/0x1501/0x1602/0x1703` | 這只固定 startup→title 時序；不把轉場 I/O 當成 menu／battle screen |
| M2.5 input timing receipt | `confirmed-runtime / harness-boundary` | `KEYINPUT=0x04000130` read stop `0x0805CF5E` → breakpoint `0x0805CF62`；16 次 `none×8/start×4/none×4` 在 breakpoint 讀回 `r0=0x03FF/0x03F7`，release 回 `0x03FF`；工具只寫 r0，沒有寫 ROM／r6／event buffer | 這證明 input value 到達 reviewed CPU path，不證明遊戲接受按鍵或自然跨 state gate |
| M2.5 stable-title natural paths | `negative / bounded-natural` | `settle=9.0s` 的 fresh `none:8,start:4,none:20` 與 `none:8,a:4,none:20` 各 32 events；builder／consumer／formatter／writer／glyph 全 0；VRAM hash `5bbfad1b...cf7463` before/after 不變 | natural cohort `0`；normal runtime table count、actual index `<44`、自然 B/E writer receipt 仍 unknown；不再延長 title-only loop |
| M2.4 normal count | `unknown / runtime-pending` | static builder source remains `[0x02014E78]` terminated by `0xFF`; harness now records bounded sentinel/count metadata only when builder is naturally entered | no natural builder hit；不能把 empty-path count 44 外推 |
| story-event E static chain | `confirmed-static / natural-runtime-pending; known-screen-cross provisional` | `tools/analyze_story_pool.py` 驗證 table boundary、27 個 entry-range literal slots、有效 Thumb caller／pair-helper／writer callsites；pointer-table SHA-256 `729b6f1e...ec6febe3`、ordered target SHA-256 `03f9d9a5...f3ad8f4`；公開夷陵／結局資料支持 E 的分支分類 | 這只證明 E 的 static consumer chain 與已知流程交叉；沒有把它當成自然 runtime glyph evidence；E source 與既有 custom units `0x8141/0x8142/0x8148/0x8158` 重疊 |
| compression | `not-confirmed` | bounded signature scan 僅得到 noisy counts：LZ77 `10744`、Huffman `6692`、RLE `4704`、Diff `4966` | 沒有把任何 signature 當成文本壓縮；需由 code／runtime 呼叫證實 |
| 可逆回插 | `record-level-bounded` | `verify_table_b_roundtrip.py` 對 table B 44/44 decode→Shift-JIS encode byte-identical、hash-identical、control-invariant；Table B／event-system D／pool A selected records 與 story E 000/001/002/003/004/005/006/007/008/009/010/011/012/013/014/015/016/017/018/019/020/021/022/023/024/025/026/027/028/029/030/031/032 另有 fixed-slot patch、re-extract、pointer-table invariant 和 BPS apply receipts | 只證明 reviewed record／pool layer；尚未證明 table relocation、全 ROM encoder、字庫覆蓋、全池抽出→回插 round trip 或自然畫面 QA |
| 翻譯 ledger | `confirmed-static / bounded-ai-review` | Table B／event-system D／pool A／story-event E 共二十八批、108 筆 source-free rows；各自 source hash、`zh-TW` target、上下文和 `ai_review` 均可由 ignored source table restore，二十八批 strip 輸出逐 byte 相同 | pool A 尚有 115 個 unique records，story-event E 33/33 已有 record-level rows；C 與完整劇情／武將／地名／官職／策略專名仍未建立完整批次；自然畫面 QA 尚未完成 |

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
| patched runtime QA | `confirmed-runtime / controlled-only; natural-pending` | 自有 mGBA PID `83841`／native port `2346` readiness、single GDB connection 通過；patched fixed-slot B0 的 controlled consumer 取得 index `0`、wrapper／formatter／writer、3 組 glyph cache→VRAM→tilemap hash receipts；`0x9594`／index `1301` identity 為 U+90E8 | 自然 8-event slice 仍 builder／consumer／pipeline 全 0；controlled receipt 不可冒充自然 menu／battle reachability，其他 code units 的 identity 未由 hash 推論 |

此 bounded batch 使「固定槽位的局部 encoder／BPS／re-extract」成立，但不解除自然
event index `<44`、完整字型／版面、pool A/C/D 翻譯、全量回插或 mGBA QA 的缺口。

## M3 bounded batch 2／Table B coverage extension（2026-08-16）

完整欄位、命令和限制見 [`research/m3-batch2-roundtrip-20260816.md`](m3-batch2-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 batch 2 的日文 source 或 work artifact。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| batch 2 ledger | `confirmed-static / ai-review` | `translations/table-b-batch-2.jsonl` 有 19 筆 unique Table B rows；restore→strip 逐 byte 相同，19 筆均無 `source` 欄位 | battle-effect 語意與 `攻勢／防護` 等用詞仍須術語／畫面審核；不是劇情或武將批次 |
| strict encoder／font coverage | `confirmed-static / bounded` | `covered_count=19`、`fit_count=19`、missing codepage entry `0`；各 target 均通過現有 1834-entry codepage、兩組 glyph bank 和原 fixed span | batch 2 本身不含 custom glyph；withheld B20 已由後續 custom batch 3 另行驗證 |
| fixed-slot Table B patch | `confirmed-static / bounded` | 44-entry pointer table unchanged；19 unique targets、changed bytes `238`；selected re-extract `19/19`、fixed-slot `19/19`，unselected records byte-identical | 仍只證明 Table B selected record layer；沒有 relocation、全池 encoder 或自然 runtime gate |
| BPS build/apply | `confirmed-static / bounded` | BPS `329` bytes；source CRC32 `a4a1c956`、target CRC32 `0e327fc6`、patch CRC32 `9cb20352`；BPS SHA-256 `a62f629e6019198761cfb01c0dcb5a241c07f7f69282261db077875f30fb963a`；套用結果與 patched ROM `cmp` 相等，patched SHA-256 `6cbbaa3b291cd02adcac442c30ded5661a84d0bd5d7265e10160175ea047987a` | 產物留 ignored／暫存，不把 ROM 或 BPS 提交；全池重抽取仍未完成 |
| batch 2 runtime | `pending / natural-not-observed` | 既有 patched B0 controlled receipt 不變，harness 明確分隔 fixed-slot variant 與 natural mode | 尚未取得 batch 2 的自然 menu／battle scene receipt；不能以 controlled fixture 擴大自然結論 |

batch 1／2 的 existing-codepage rows 覆蓋 Table B `25/26` unique records；B20 後續以
明確 licensed custom glyph mapping 另行處理，沒有偷偷回退成日文字形。

## M3 event-system batch 1／pool D fixed-slot round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-event-system-batch1-roundtrip-20260816.md`](m3-event-system-batch1-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 D pool 日文 source 或 work artifact。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| event-system ledger | `confirmed-static / ai-review` | `translations/event-system-batch-1.jsonl` 有 9 個 source-free rows；每筆有 string ID、source hash、`zh-TW` target、上下文、max width、控制碼清單和 `ai_review` 狀態；restore→strip 逐 byte 相同 | batch 1 當時 D pool 尚有 7 個 unique targets，已由 batch 2 處理 6 個；剩 1 個空字串 target，仍需自然 menu／ending 畫面核對 |
| pool D structure | `confirmed-static / bounded` | file base `0x0D4D00`、28 entries、16 unique targets；28/28 NUL／Shift-JIS 結構可解；payload length distribution 為 0-byte `6`、4-byte `15`、6-byte `2`、10-byte `3`、12-byte `2` | 這是 D pool 的結構邊界，不等於所有 pool 或自然呼叫點已定位 |
| strict encoder／font coverage | `confirmed-static / bounded` | 9/9 目標通過 strict Shift-JIS、1834-entry codepage、兩組 0x20-byte glyph slot 和原 fixed span；missing codepage entry `0` | 僅限 batch 1 的 9 rows；batch 2 的 custom glyph rows、其餘 D/A/C pool 與版面規則另行 pending |
| fixed-slot pool D patch | `confirmed-static / bounded` | 28-entry pointer table unchanged；9 unique targets、changed bytes `34`；relocation disabled；selected re-extract `9/9`、fixed-slot `9/9`，unselected records byte-identical，ROM size unchanged | 只證明 selected D record/table layer，不是全池 relocation／全遊戲 encoder proof |
| BPS build/apply | `confirmed-static / bounded` | BPS `78` bytes；source CRC32 `a4a1c956`、target CRC32 `510f7391`、patch CRC32 `0c4e4642`；BPS SHA-256 `c390363916b70f034741f4e83042a35887dfb164dbf82205101aa6a097141551`；套用結果與 patched ROM `cmp` 相等，patched SHA-256 `9ee608623a6476695710e833e9185b9cfde43f6c5c930413c1d6069b06efd4e7` | 產物留 ignored／暫存；未在自然 D menu／ending 畫面做 mGBA QA |
| D runtime | `pending / natural-not-observed` | 本切片未把 Table B controlled receipt 擴大到 D pool；runtime evidence boundary 保持分開 | 尚未取得 D menu／event 的自然 formatter→glyph cache→VRAM／tilemap receipt |

這個批次使 pool D selected records 的 source-safe ledger、fixed-slot encoder、re-extract
和 BPS apply 成立，但不解除自然 event index `<44`、完整 D/A/C pool 翻譯、字型缺字、
全量回插或 mGBA QA 的缺口。

## M3 event-system batch 2／custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-event-system-batch2-roundtrip-20260816.md`](m3-event-system-batch2-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 D pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| event-system batch 2 ledger | `confirmed-static / ai-review` | 6 個 source-free unique rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | 仍需自然 menu／ending 畫面與人工 zh-TW UI 用語審核 |
| custom encoder／plane gate | `confirmed-static / bounded` | `custom_glyph_patch.py` 使用 8-entry licensed mapping；6 custom glyph plane match；D selected 12/12 entries re-extract／fixed-slot 相符；changed bytes `360`；pointer／codepage table unchanged | raw code-unit non-use 只限四池 decoded source table；secondary plane zero-filled 的美術可讀性仍待 runtime |
| BPS build/apply | `confirmed-static / bounded` | BPS `493` bytes；source CRC32 `a4a1c956`、target CRC32 `e3c08899`、patch CRC32 `a5138722`；BPS SHA-256 `22efbb238ad5d0b406c7f6768fd9055881ddfdbfd04390b739a5d2ca40d5276b`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；未取得自然 D menu receipt |
| D batch 2 runtime | `pending / natural-not-observed` | 沿用自然 cohort `0` 的 evidence boundary；未把 custom fixture 當自然證據 | 尚未取得 D custom glyph formatter→cache→VRAM／tilemap 的自然 receipt |

## M3 Table B batch 3／withheld custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見 [`research/m3-batch3-roundtrip-20260816.md`](m3-batch3-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 B20 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| batch 3 ledger | `confirmed-static / ai-review` | 1 個 source-free B20 row；schema pass；restore→strip 逐 byte 相同，source fields `0` | battle wording、單行寬度和 custom glyph 可讀性仍需自然戰役／策略畫面審核 |
| custom encoder／plane gate | `confirmed-static / bounded` | `U+7D93`／`U+9A57` mapping；2 custom glyph plane match；selected re-extract／fixed-slot `1/1`；changed bytes `120`；44-entry pointer／codepage table unchanged | raw code-unit non-use 只限四池 decoded source table；不代表全 ROM 或自然 runtime |
| BPS build/apply | `confirmed-static / bounded` | BPS `186` bytes；source CRC32 `a4a1c956`、target CRC32 `0fe59122`、patch CRC32 `8ab07150`；BPS SHA-256 `419624c1cd99958d2d45ae521078ca29a5485ad09c37ad127447b69139534120`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；全池／全 ROM round-trip 仍未完成 |

## M3 system-item/class batch 1／pool A custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-system-item-class-batch1-roundtrip-20260816.md`](m3-system-item-class-batch1-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 pool A 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| pool A batch 1 ledger | `confirmed-static / ai-review` | `translations/system-item-class-batch-1.jsonl` 有 4 個 source-free description rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | system-item/class pool 仍有 149 unique records未翻譯；兩行 wording／item terminology 仍待人工與畫面審核 |
| pool A boundary／patch | `confirmed-static / bounded` | file base `0x0CBC54`、183 entries；4 unique targets、selected aliases `5` entries；pointer table unchanged；unselected records byte-identical；changed bytes `161` | 僅證明 selected pool-A record layer，不是全 pool A encoder 或完整 layout proof |
| custom glyph／re-extract | `confirmed-static / bounded` | U+6548 由 licensed mapping／Unifont-T plane 提供；custom plane match `1/1`；selected re-extract／fixed-slot `5/5`；format／control invariant 保持 | raw code-unit non-use 只限四池 decoded source table；自然 item screen receipt、全池 glyph coverage 仍 pending |
| BPS build/apply | `confirmed-static / bounded` | BPS `220` bytes；source CRC32 `a4a1c956`、target CRC32 `64b494f2`、patch CRC32 `0cd7c391`；BPS SHA-256 `a27b0b81cd72358a8b65e73e4635454f3660c1a8d7a6b18ad547484e46902391`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；未在自然 item screen 做 mGBA QA |

## M3 system-item/class batch 2／pool A class-conversion round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-system-item-class-batch2-roundtrip-20260816.md`](m3-system-item-class-batch2-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 pool A 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| pool A batch 2 ledger | `confirmed-static / ai-review` | `translations/system-item-class-batch-2.jsonl` 有 6 個 source-free rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | class wording、兵種名稱和兩行 layout 仍待人工／畫面審核 |
| pool A custom encoder／re-extract | `confirmed-static / bounded` | 5 個 licensed custom glyph plane match；selected re-extract／fixed-slot `6/6`；changed bytes `455`；183-entry pointer table unchanged，未選取 records byte-identical | 僅限 selected class-conversion records；raw code-unit non-use 只限四池 decoded source table |
| BPS build/apply | `confirmed-static / bounded` | BPS `565` bytes；source CRC32 `a4a1c956`、target CRC32 `c6e49fa8`、patch CRC32 `58005e2e`；BPS SHA-256 `2f47ea59b9435dfc72ae155fb142584eaab0c06cd1a75d63e0ae0ceced03839e`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；自然 item／class screen QA 未完成 |

## M3 system-item/class batch 3／pool A level-gated conversion round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-system-item-class-batch3-roundtrip-20260816.md`](m3-system-item-class-batch3-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 pool A 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| pool A batch 3 ledger | `confirmed-static / ai-review` | `translations/system-item-class-batch-3.jsonl` 有 12 個 source-free rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | `投石車`／`發石車` 等 wording、兵種名稱與兩行 layout 仍待人工／畫面審核 |
| pool A custom encoder／re-extract | `confirmed-static / bounded` | 8 個 licensed custom glyph plane match；selected re-extract／fixed-slot `12/12`；changed bytes `812`；183-entry pointer table unchanged，未選取 records byte-identical | 僅限 selected level-gated/class records；raw code-unit non-use 只限四池 decoded source table |
| BPS build/apply | `confirmed-static / bounded` | BPS `973` bytes；source CRC32 `a4a1c956`、target CRC32 `4fbe6c36`、patch CRC32 `231c8389`；BPS SHA-256 `8448c1151be5f4a794064723ac98cc8df837ae9dbd356c731d51e059bdc43bdc`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；自然 item／class screen QA 未完成 |

## M3 system-item/class batch 4／pool A recovery round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-system-item-class-batch4-roundtrip-20260816.md`](m3-system-item-class-batch4-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 pool A 日文 source、work 或 patched ROM。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| pool A batch 4 ledger | `confirmed-static / ai-review` | `translations/system-item-class-batch-4.jsonl` 有 6 個 source-free rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | 恢復量 wording、兩行 layout 與 item screen 語境仍待人工／畫面審核 |
| pool A existing-codepage encoder／re-extract | `confirmed-static / bounded` | existing codepage coverage `6/6`；custom glyph count `0`；selected alias 展開後 re-extract／fixed-slot `31/31`；changed bytes `195`；183-entry pointer table unchanged，未選取 records byte-identical | 僅限 selected recovery records；raw code-unit non-use 與自然畫面仍不外推 |
| BPS build/apply | `confirmed-static / bounded` | BPS `257` bytes；source CRC32 `a4a1c956`、target CRC32 `e4b23029`、patch CRC32 `c0b987dc`；BPS SHA-256 `7ca7f5c6bf6c6efa24ab68c01dff31b712f54067c9e6258bc539820fc3e8dd66`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；自然 item／class screen QA 未完成 |

## M3 system-item/class batch 5／pool A battle-state round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-system-item-class-batch5-roundtrip-20260816.md`](m3-system-item-class-batch5-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 pool A 日文 source、work 或 patched ROM。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| pool A batch 5 ledger | `confirmed-static / ai-review` | `translations/system-item-class-batch-5.jsonl` 有 6 個 source-free rows；schema pass；restore→strip 逐 byte 相同，source fields `0` | `失序`／`恢復正常` 等 wording 沿用已審核 battle-effect label，仍待人工／自然畫面審核 |
| pool A existing-codepage encoder／re-extract | `confirmed-static / bounded` | existing codepage coverage `6/6`；custom glyph count `0`；selected re-extract／fixed-slot `6/6`；changed bytes `114`；183-entry pointer table unchanged，未選取 records byte-identical | 僅限通用 battle-state records；帶策略專名、raw code-unit non-use 與自然畫面仍不外推 |
| BPS build/apply | `confirmed-static / bounded` | BPS `167` bytes；source CRC32 `a4a1c956`、target CRC32 `632d9602`、patch CRC32 `cef2cb2c`；BPS SHA-256 `0dffb017f7de40474efcdb8b2c895cb4e72a6e9b49e9cb3cf363e93ae20dc8b1`；套用結果與 patched ROM `cmp` 相等 | 產物留 ignored／暫存；自然 item／battle screen QA 未完成 |

## M3 custom glyph format／mapping gate（2026-08-16）

`research/m3-custom-glyph-format-20260816.md` 記錄 licensed input、mapping scope、
custom-aware encoder 和 hash-only verifier；本帳不保存 raw glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| licensed source／mapping | `confirmed-static / bounded` | Unifont-T 17.0.05 SHA-256 `c1768bd7...f46c5b53`，SIL OFL 1.1；17 個 Unicode→existing raw code unit／codepage index mapping 經 ROM table identity 與四池 source non-use gate | source non-use 不是 full-ROM proof；未提交字型 bytes |
| custom plane conversion | `confirmed-static / bounded` | 16×16 bitmap→primary 0x20-byte plane、secondary zero plane；D batch 2 6/6、Table B batch 3 2/2、pool A batch 1 1/1、batch 2 5/5、batch 3 8/8 plane match | secondary plane 的美術可讀性、selector／palette 變體與自然 runtime 仍 pending |
| custom-aware round-trip | `confirmed-static / bounded` | custom patch／verify 工具保留 record／glyph spans、pointer／codepage table invariant，並完成 D／B custom fixture 與 pool A 三批 formal BPS apply | 全池 A/B/C/D、自然 formatter→VRAM、全 ROM raw code-unit audit 和發布 patch 尚未完成 |

## M3 glyph format cross-check（2026-08-16）

`research/m3-font-format-20260816.md` 記錄逐指令 glyph expander 與 hash-only
cross-check；本帳不保存 raw glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| two-plane source format | `confirmed-static` | `0x080650DC–0x08065254` 每個 codepage slot 讀兩組 `0x20` bytes，按 selector masks 合成 `0x80`-byte cache；source bases `0x08232BCC`／`0x0822468C` | 只確認 reviewed SJIS renderer path；其他 selector／palette 情境仍 pending |
| static→runtime cache cross-check | `confirmed-controlled-runtime` | index `1301`／`0x9594`／selector `0` 的 static expanded hash `e56e457e...` 與 controlled cache hash 相同；`font_glyph_format.py` + 3 tests 可重跑 | hash 是 addressing／byte consistency receipt，不單獨證明其他 Unicode identity |
| custom zh-TW glyph insertion | `confirmed-static / bounded` | `m3-custom-glyph-map.json` 固定 17 個 Unicode→existing codepage raw unit／index；licensed Unifont-T source hash、plane conversion、fixed-slot patch、custom-aware re-extract 與 formal custom BPS receipts 已通過 | full-ROM raw-code-unit non-use、全池 coverage、secondary-plane art QA、自然畫面 runtime 和正式發行 patch 仍 pending |

`font_slot_audit.py` 的 bounded source-pool audit 另確認 259 筆 decoded records 使用 228
個 unique double-byte code units；17 個 mapping 已從這個 bounded non-use cohort 選定並經
custom-aware verifier 使用，但不升格為 full-ROM non-use proof。
詳見 [`research/m3-font-slot-audit-20260816.md`](m3-font-slot-audit-20260816.md)。

## M3 story-event pool E static chain（2026-08-16）

Story-event E 的完整 bounded 結論見
[`research/m3-story-pool-static-chain-20260816.md`](m3-story-pool-static-chain-20260816.md)。
本帳只保留可審核的摘要，不保存 E 的日文 payload。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| E table boundary | `confirmed-static / bounded` | file `0x0cdb64`、33 entries、33 unique targets、target `0x077328–0x077e68`；前 word `0x00030003`、next word `0x19010502`、following `0x02000000` | 鄰近資料的完整語意尚未命名 |
| E record structure | `confirmed-static` | 33/33 strict Shift-JIS、32/33 LF、0 opaque controls、payload length `18–124` bytes；hash-only manifest 已記錄 | 跨 record LF fragment 的翻譯語境需逐批核對；不是 full script |
| E static consumer | `confirmed-static / natural-runtime-pending` | `0x080cdb64 → 0x08011904 → 0x080118c8 → 0x0800cad8`；27 個 literal slots 通過 entry range／alignment；有效 Thumb callsites 經 analyzer 驗證 | 尚無 E 自然 formatter→glyph cache→VRAM／tilemap receipt |
| E decoder scope | `confirmed-static / explicit-opt-in` | 預設四池仍是 259 records；`--include-story` 才產生 292-record ignored source table；known-screen-cross 文件分開記錄公開結局流程 | 原文仍只留 ignored；外部流程不替代自然 runtime glyph receipt |
| E custom unit safety | `confirmed-static / bounded` | E source 使用 `0x8141`、`0x8142`、`0x8148`、`0x8158`，與既有 17-map unit 重疊；E-specific map 以 292-record source-use cohort 選 index 15／16／23／24／25／26／27／28／32／34／35／36，batch 3／4／5／6／8／9／10／11／12／13／14／15／17 custom plane `3/3`／`4/4`／`5/5`／`5/5`／`4/4`／`4/4`／`3/3`／`2/2`／`1/1`／`2/2`／`1/1`／`2/2`／`4/4` | raw-unit non-use 仍不是 full-ROM proof；secondary plane／自然 runtime 可讀性仍 pending |

## M3 story-event E batch 1／existing-codepage round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch1-roundtrip-20260816.md`](m3-story-event-batch1-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 patched ROM。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger | `confirmed-static / ai-review` | `translations/story-event-batch-1.jsonl` 有 E:002、E:011 兩筆 source-free rows；restore 成功，schema／strip 後 source fields `0`；術語使用 `蜀`、`劉備` 的既有臺灣三國志候選 | 仍待自然 ending／戰役畫面與人工最終術語審核；不是完整 E pool 翻譯 |
| existing-codepage／layout gate | `confirmed-static / bounded` | strict codepage coverage `2/2`、原始 span fit `2/2`、各保留一個 LF；ASCII `?` 避開 `0x8148` custom overlap；17-unit custom guard overlap `0` | 不代表 E 其它 records 或 custom glyph 可用；自然 writer／tilemap 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | `patch_fixed_pool.py --pool story-event` changed `94` bytes；E pointer table unchanged；selected re-extract／fixed-slot `2/2`，未選 record byte-identical；relocation disabled | 只覆蓋 E:002、E:011 |
| BPS build/apply | `confirmed-static / bounded` | BPS `132` bytes；source CRC32 `a4a1c956`、target CRC32 `210328ca`、BPS CRC32 `de6bc4b7`；BPS SHA-256 `499ce1633001862375528e8c18b7c49440bc54c46b384868ab3912227960e7df`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `9e931540ee087c25cbd1623b21a891f438f7c23813547c60cea52b50c598c757` | 產物留 ignored／暫存；mGBA 畫面 QA 尚未完成 |

## M3 story-event E batch 2／existing-codepage round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch2-roundtrip-20260816.md`](m3-story-event-batch2-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 patched ROM。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger | `confirmed-static / ai-review` | `translations/story-event-batch-2.jsonl` 有 E:032 一筆 source-free row；restore 成功，schema／strip 後 source fields `0`；`漢朝` 已加入臺灣術語候選 | 結局語句仍待自然畫面與人工終審；不是完整 E pool 翻譯 |
| existing-codepage／layout gate | `confirmed-static / bounded` | strict codepage coverage／fit `1/1`；保留 3 LF、無其它控制碼；ASCII punctuation 避開 custom overlap；17-unit guard overlap `0` | 不代表 E 其它 records 或 custom glyph 可用；自然 writer／tilemap 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | changed `81` bytes；E pointer table unchanged；selected re-extract／fixed-slot `1/1`，未選 record byte-identical；relocation disabled | 只覆蓋 E:032 |
| BPS build/apply | `confirmed-static / bounded` | BPS `117` bytes；source CRC32 `a4a1c956`、target CRC32 `8b229520`、BPS CRC32 `785079cd`；BPS SHA-256 `602ff6cfc2e3bb4fe9c36b8a5502470fcbce97ac76bef3c37ffd99502ed314ea`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `77ad02e63074b8ca93c31da250dcdfea09de96c222d27536b1962cbf440ecb21` | 產物留 ignored／暫存；mGBA 固定 2345 socket negative，沒有 E runtime receipt |

## M3 story-event E batch 3／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch3-roundtrip-20260816.md`](m3-story-event-batch3-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-3.jsonl` 有 E:003、E:004 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` 的 line budget／control／fit 為 `2/2`；同一歷史結局分支有公開流程交叉證據 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 的 U+7B49／U+537B／U+570B 對 indices 15／16／23；292-record bounded source-use non-use；custom plane `3/3`；target codepage membership gate `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `321` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:003、E:004 |
| BPS build/apply | `confirmed-static / bounded` | BPS `406` bytes；source CRC32 `a4a1c956`、target CRC32 `20bb7ad7`、BPS CRC32 `768c2f07`；BPS SHA-256 `0df4a3ee708d67acc64d70298134650113b66f284272dec6127476de8f7ba046`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `8353e8a194aac965dfcd75915c6619ba0feecaa322b7393f96266ee84aedc65d` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 4／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch4-roundtrip-20260816.md`](m3-story-event-batch4-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-4.jsonl` 有 E:005 一筆 source-free row；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `1/1`；與 batch 3 同一已知結局流程分組 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 新增 U+5433；292-record bounded source-use non-use；custom plane `4/4`；target codepage membership `1/1` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `259` bytes；selected re-extract／fixed-slot `1/1`；unselected records byte-identical；relocation disabled | 只覆蓋 E:005 |
| BPS build/apply | `confirmed-static / bounded` | BPS `340` bytes；source CRC32 `a4a1c956`、target CRC32 `1d37a056`、BPS CRC32 `ba654c13`；BPS SHA-256 `5341b6775477c36ce7b02599eb5b5d5382c82408b6fbc4f0ebfda8a3b58db4cc`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `2547ef9b2c30d05a35cab78af76c28a8432e5cbb0e37a2c1b9fc81d6b5d7b16d` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 5／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch5-roundtrip-20260816.md`](m3-story-event-batch5-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-5.jsonl` 有 E:006 一筆 source-free row；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `1/1`；與 batch 3／4 同一已知結局流程分組 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+5433／U+5F9E／U+6B64／U+53EA／U+65BC 對 indices 24／25／26／27／28；292-record bounded source-use non-use；custom plane `5/5`；target codepage membership `1/1` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `315` bytes；selected re-extract／fixed-slot `1/1`；unselected records byte-identical；relocation disabled | 只覆蓋 E:006 |
| BPS build/apply | `confirmed-static / bounded` | BPS `399` bytes；source CRC32 `a4a1c956`、target CRC32 `f1452014`、BPS CRC32 `202b0259`；BPS SHA-256 `62c8b55daeb2a76f980f2f6fb7216a9970b621fd51ca831cdf5279403ed755ea`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `75bc199c2a655172c2545396181c380838731299463384eec32477c68e6a9f9` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 6／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch6-roundtrip-20260816.md`](m3-story-event-batch6-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-6.jsonl` 有 E:007、E:008 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；與 batch 3–5 同一已知結局流程分組 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+95DC／U+7B49／U+5433／U+570B／U+6B64 對 indices 32／15／24／23／26；292-record bounded source-use non-use；custom plane `5/5`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `408` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:007、E:008 |
| BPS build/apply | `confirmed-static / bounded` | BPS `508` bytes；source CRC32 `a4a1c956`、target CRC32 `04ffcd87`、BPS CRC32 `8945c99b`；BPS SHA-256 `f9c8890024ac425c04879538c37f896c1ea6adfddde49474915152e185434d30`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `cea14476b02ee25b7a9c81de9260047a07e1901f36873aa90994f64389a376f3` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 7／existing-codepage round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch7-roundtrip-20260816.md`](m3-story-event-batch7-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 patched ROM。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-7.jsonl` 有 E:009、E:010 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；與 batch 3–6 同一已知結局流程分組 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| existing-codepage gate | `confirmed-static / bounded` | target codepage membership `2/2`；無新增 E custom glyph；5 行／4 行保留、max width `12`；E-specific source-use gate 未被擴大 | conservative line budget 不等於 pixel-width proof；自然 writer／tilemap 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `215` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:009、E:010 |
| BPS build/apply | `confirmed-static / bounded` | BPS `252` bytes；source CRC32 `a4a1c956`、target CRC32 `20c92a7f`、BPS CRC32 `eb43ac96`；BPS SHA-256 `d56325c661f22197c39fc2a1ea476d6429afea2b01cbc567f18bbb16ca3fb907`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `ba894053ccaf6bb2d1c722822174b3bfb6252da2f6d928e44b7b839066bed7ac` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 8／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch8-roundtrip-20260816.md`](m3-story-event-batch8-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-8.jsonl` 有 E:012、E:013 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；另一條結局敘事分支 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 新增 U+737B／U+4E82 對 indices 34／35，並重用 U+95DC／U+570B indices 32／23；292-record bounded source-use non-use；custom plane `4/4`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `393` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:012、E:013 |
| BPS build/apply | `confirmed-static / bounded` | BPS `490` bytes；source CRC32 `a4a1c956`、target CRC32 `d5b570ef`、BPS CRC32 `8c35c5ab`；BPS SHA-256 `08d34403808810eb6dea9bdf10de5c54d146bb211c0dffd959dea5f7be0b1a6b`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `5187703988e1fd843223244b72087c381e823364b3fe51d7febb71e00eba997c` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 9／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch9-roundtrip-20260816.md`](m3-story-event-batch9-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-9.jsonl` 有 E:014、E:015 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；夷陵／吳蜀衝突分支分類有公開流程背景 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 的 U+537B／U+5433／U+570B／U+95DC 對 indices 16／24／23／32；292-record bounded source-use non-use；custom plane `4/4`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `369` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:014、E:015 |
| BPS build/apply | `confirmed-static / bounded` | BPS `460` bytes；source CRC32 `a4a1c956`、target CRC32 `e8cb653e`、BPS CRC32 `8593a042`；BPS SHA-256 `8fb6ff4e744040c41dcd64a039bc4a13396ca2d8ef0a381e84dcb8699ae4809f`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `a4f477518e1b264e92d9dab6d5546800ba63871d6446f39d39d41be57c99b03e` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 10／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch10-roundtrip-20260816.md`](m3-story-event-batch10-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-10.jsonl` 有 E:016、E:017 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；與夷陵／吳蜀衝突分支的公開流程分類相符 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+570B／U+5433／U+4E82 對 indices 23／24／35；292-record bounded source-use non-use；custom plane `3/3`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `336` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:016、E:017 |
| BPS build/apply | `confirmed-static / bounded` | BPS `412` bytes；source CRC32 `a4a1c956`、target CRC32 `6b419e2e`、BPS CRC32 `9be23232`；BPS SHA-256 `4713ea311908c74978a3372dac76c1327482e66cbdaeeb0bcf3e2161513623b1`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `2cba927d4c4facc3e82f4721f6927069b5a21f459214448d579c1e05a3cccae5` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 11／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch11-roundtrip-20260816.md`](m3-story-event-batch11-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-11.jsonl` 有 E:018、E:019 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；漢朝復興／玉璽敘事分組有歷史流程背景 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+737B／U+570B 對 indices 34／23；292-record bounded source-use non-use；custom plane `2/2`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `210` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:018、E:019 |
| BPS build/apply | `confirmed-static / bounded` | BPS `282` bytes；source CRC32 `a4a1c956`、target CRC32 `30d7082b`、BPS CRC32 `2144df1c`；BPS SHA-256 `8ba507ddb3ea0cd53e946ee1a2b3573fdc1551ab803b343770a7ed1547a84ce6`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `86f6faddd2bad0825a8c973fdcd6b18df72f03b41e73c07a7e99a5af50ddd27f` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 12／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch12-roundtrip-20260816.md`](m3-story-event-batch12-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-12.jsonl` 有 E:020、E:021 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；漢朝衰退／劉備掌權敘事分組有歷史流程背景 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+737B 對 index 34；292-record bounded source-use non-use；custom plane `1/1`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `185` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:020、E:021 |
| BPS build/apply | `confirmed-static / bounded` | BPS `247` bytes；source CRC32 `a4a1c956`、target CRC32 `b73ae1c4`、BPS CRC32 `2144df1c`；BPS SHA-256 `f396b91860602039f992c0ae9b8047c0dedece30431c0e3275af85d09f35da2c`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `403a5e9f620fff53ac4deaa6724564769d4d94945332328d9c306003deae43d5` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 13／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch13-roundtrip-20260816.md`](m3-story-event-batch13-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-13.jsonl` 有 E:022、E:023 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；劉備掌權／反叛退位敘事分組有歷史流程背景 | 仍待自然 ending 畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+4E82／U+6B64 對 indices 35／26；292-record bounded source-use non-use；custom plane `2/2`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `233` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:022、E:023 |
| BPS build/apply | `confirmed-static / bounded` | BPS `298` bytes；source CRC32 `a4a1c956`、target CRC32 `4857d6d9`、BPS CRC32 `2144df1c`；BPS SHA-256 `64e24dbd7392c4ecdb294a467eac921adcc50655679080c9f8cad1e5e6fdf4bb`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `1931d2bdf048a4c3a19f8f3eab73becfa6b9f5e2a4a6602579a31c82cf484900` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 14／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch14-roundtrip-20260816.md`](m3-story-event-batch14-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-14.jsonl` 有 E:024、E:025 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；漢朝復興、劉備安定生活與冷落片段分組有公開流程背景 | 仍待自然結局畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+537B 對 index 16；292-record bounded source-use non-use；custom plane `1/1`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `153` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:024、E:025 |
| BPS build/apply | `confirmed-static / bounded` | BPS `206` bytes；source CRC32 `a4a1c956`、target CRC32 `877bc6fd`、BPS CRC32 `1f853700`；BPS SHA-256 `10f35a6ced9e3f719e8a049354cd258e74884d7e6e945d81fceb8cd4763b0097`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `56ac1674e2af9adb8c4c1fded7b1bead406493b6c1a9eefe35fd798af9637c6f` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 15／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch15-roundtrip-20260816.md`](m3-story-event-batch15-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-15.jsonl` 有 E:026、E:027 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；遭冷落人物、刺殺與劉備信念轉折分組有公開流程背景 | 仍待自然結局畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+7B49／U+4E82 對 indices 15／35；292-record bounded source-use non-use；custom plane `2/2`；target codepage membership `2/2` | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `269` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:026、E:027 |
| BPS build/apply | `confirmed-static / bounded` | BPS `342` bytes；source CRC32 `a4a1c956`、target CRC32 `67e4781e`、BPS CRC32 `472c1774`；BPS SHA-256 `147b6c6c070e82afe057665dc7f5a34c4e393db73885d7355b7c293157b6bf3d`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `ff27438637ce0e72b906e051471d423b6e23ceaf70d90e474eb286f7cf848d6d` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 16／existing-codepage round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch16-roundtrip-20260816.md`](m3-story-event-batch16-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-16.jsonl` 有 E:028、E:029 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；宮廷腐敗、董卓類比與劉備節約政策分組有公開流程背景 | 仍待自然結局畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| existing codepage gate | `confirmed-static / bounded` | existing B3EJ codepage coverage `2/2`；無新增 E custom glyph；五行／四行保留、max width `13`／`12` | conservative line budget 不等於 pixel-width proof；自然 writer／tilemap 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `203` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:028、E:029 |
| BPS build/apply | `confirmed-static / bounded` | BPS `242` bytes；source CRC32 `a4a1c956`、target CRC32 `b8f1a8d2`、BPS CRC32 `997a7b26`；BPS SHA-256 `469068a4d36efde44fb03cdcee8d8bc2ac28cb000a37216a8927ec68811c5a57`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `bc5ac30f1915b2a31ea1df438846212b30e42dbf3718702b43a02464dabe98ea` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 17／E-specific custom glyph round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch17-roundtrip-20260816.md`](m3-story-event-batch17-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-17.jsonl` 有 E:030、E:031 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；獻帝離宮、劉備失國與漢王朝復興分組有公開流程背景 | 仍待自然結局畫面與人工 zh-TW 終審；不是完整 E pool 翻譯 |
| E custom encoder／plane gate | `confirmed-static / bounded` | E-specific map 使用 U+737B／U+6B0A／U+570B／U+65BC 對 indices 34／36／23／28；292-record bounded source-use non-use；custom plane `4/4`；target codepage membership `2/2`；新增 U+6B0A 候選 raw `0x8256`／index `36` 的 source-use receipt | raw-unit non-use 不是 full-ROM proof；secondary plane、版面和自然 writer 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `380` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:030、E:031 |
| BPS build/apply | `confirmed-static / bounded` | BPS `480` bytes；source CRC32 `a4a1c956`、target CRC32 `62569c89`、BPS CRC32 `0b8ea7ac`；BPS SHA-256 `3e2648a251b056dc91a6ec93d247290bec776e1f1a311e67f4d0ba1ded5a4f6c`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `bce7799bc61eb64cf4438b3222cccc7af2e2aa497d10e8c7fd7f4d042555a098` | 產物留 ignored／暫存；E 自然 formatter→cache→VRAM receipt 仍 pending |

## M3 story-event E batch 18／existing-codepage round-trip（2026-08-16）

完整欄位、命令和限制見
[`research/m3-story-event-batch18-roundtrip-20260816.md`](m3-story-event-batch18-roundtrip-20260816.md)。
本帳只補充 hash／計數，不保存 E pool 日文 source、work 或 generated glyph bytes。

| 項目 | 狀態 | 已有證據 | 尚未證實／限制 |
|---|---|---|---|
| story ledger／layout | `confirmed-static / ai-review` | `translations/story-event-batch-18.jsonl` 有 E:000、E:001 兩筆 source-free rows；restore／strip 逐 byte 相同，source fields `0`；`audit_story_layout.py` line budget／control／fit `2/2`；劉備臨終、桃園結義誓言與安詳離世分組有公開流程背景 | 仍待自然結局畫面與人工 zh-TW 終審；不是自然 runtime 完成證明 |
| existing codepage gate | `confirmed-static / bounded` | existing B3EJ codepage coverage `2/2`；無新增 E custom glyph；四行／五行保留、max width `13` | conservative line budget 不等於 pixel-width proof；自然 writer／tilemap 仍 pending |
| fixed-slot re-extract | `confirmed-static / bounded` | story E 33-entry pointer table unchanged；changed `218` bytes；selected re-extract／fixed-slot `2/2`；unselected records byte-identical；relocation disabled | 只覆蓋 E:000、E:001；全池 re-extract 仍不是全 ROM round-trip |
| BPS build/apply | `confirmed-static / bounded` | BPS `257` bytes；source CRC32 `a4a1c956`、target CRC32 `bc9b1427`、BPS CRC32 `42125eb4`；BPS SHA-256 `cd3a1f0ac18c09ee84898d684cdffdacfe52bf68d403c22de39577f6e9def09e`；apply 與 patched ROM `cmp` 相等，patched SHA-256 `44fd11a906f6698c0c66f806a60da75280f5e49ea9f58db1e221b0333c41851a` | 產物留 ignored／暫存；自然 E formatter→cache→VRAM receipt 仍 pending |

## 後續證據邊界

1. 用 ROM-independent tests 保持 identity／pointer summary 工具可重跑。
2. 若重新做 runtime，使用本 session 自己的 mGBA 進程與獨立 GDB port；只記錄寄存器、DMA、VRAM／IWRAM 範圍和可重現 breakpoint，不提交 build、probe 或 ROM。
3. 只有在同一候選字串能以 pointer／code-flow／畫面三者交叉確認後，才建立本機 ignored decoded source table。
4. 目前已對 reviewed Table B／D selected records 建立 fixed-slot custom／existing-codepage
   round-trip；只有全池未修改內容可抽出、回插、再抽出逐 byte 一致，才將 reversible
   insertion 從 `record-level-bounded` 升格為全池 confirmed。
5. 所有翻譯批次仍必須通過 `core/ledger/restore_translations.rb`、`strip_translations.rb`、
   schema、安全檢查與術語來源／人工審核。

## 尚未採用的假設

- 不假設沿用黃金太陽、光明之魂或其他 GBA 遊戲的字型、壓縮、指標、控制碼或回插格式。
- 不把公開攻略、英文／中文 patch 或 static Shift-JIS 命中當成正式逐句翻譯來源。
- 不因 header complement mismatch 自動修補 ROM，也不將它改寫成「clean」版本。
- 不把 `B3EJ` 產品代碼單獨當成 ROM 身分；本帳以 header、大小和 hash 一起核對。

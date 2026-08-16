# 《超級機器人大戰 D》偵察 ledger

本檔案只保留可審核的工程觀察、路徑、雜湊、計數與結論。日文原文、完整解碼
輸出、OCR／圖片與大量掃描 dump 不放在 Git；它們只存在本機 ignored 路徑。

## 2026-08-16：來源與 ROM 身分

| 項目 | 結果 | 證據／重跑方式 |
| --- | --- | --- |
| 候選封裝 | `roms/Original/1001-1500/1120 - 超级机器人大战D Super Robot Taisen D(JP)(Banpresto)(64Mb).zip` | ZIP 僅一個 8 MiB 成員；封裝 CRC32 `efb45117` |
| GBA title | `SRWD` | `fingerprint_rom.py` 讀 `0xa0..0xab` |
| game code | `A6SJ` | `fingerprint_rom.py` 讀 `0xac..0xaf` |
| maker／revision | `D9`／`00` | `fingerprint_rom.py` 讀 `0xb0..0xb1`／`0xbc` |
| header complement | `0x80` 儲存且計算一致 | `fingerprint_rom.py` 依 GBA header 規則重算 |
| 檔案大小 | `0x800000`（8 MiB） | `stat` 與 fingerprint |
| ROM CRC32 | `efb45117` | ZIP CRC 與檔案全量 CRC32 一致 |
| ROM SHA-256 | `12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84` | `shasum -a 256` |

身分結論：**A6SJ 候選已核對，可作本輪基準 ROM**。尚未有第二份獨立 clean dump
用來做同版本 byte-for-byte 比對，因此不把這個雜湊宣稱為外部資料庫的唯一標準
值。

## 2026-08-16：純靜態第一輪

工具：`tools/static_recon.py`；通用掃描器只作方法參照，沒有把其他遊戲的格式
套進本 ROM。

### Shift-JIS 假說

- 全 ROM 結構性掃描在門檻 8 字時得到 `64,538` 段候選；這個數量本身顯示
  「每個位元組序列可解成 Shift-JIS」的判定太寬，不能當成文本證據。
- 兩段候選具有特別不同的形狀：
  - `0x7cb55c..0x7cc34a`：3566 bytes、1783 個解碼字符、1783 個 unique。
  - `0x7dfb46..0x7e0366`：2080 bytes、1040 個解碼字符、1040 個 unique。
- 它們是逐字唯一的長字符序列，不像一般直接對話；目前暫列為**字符表候選**。
  找到其來源／使用呼叫鏈前，不把其順序當成 codepage，也不把其中字符身分
  直接寫入翻譯資料。
- 標準 Shift-JIS 常見 UI sentinel（例如「はい」「いいえ」「レベル」「たたかう」
  等）沒有得到連續明文命中。這只排除「常見詞以標準 Shift-JIS 原樣散落」的
  簡單假說，不能排除自訂雙位元組碼頁或壓縮後再解碼。

### 指標假說

- 4-byte little-endian、halfword-aligned、值落在本 ROM 映射範圍的非遞減候選有
  `168` 段（最小 8 words）。最大候選位於 `0x058484`，485 words，但首尾只跨
  `0xe8`；另有 `0x1186c4` 345 words 與 `0x0f42cc` 176 words。
- 這些候選尚未以 caller／資料內容／字串邊界交叉確認；目前只能記為 literal／
  jump table／資料表候選，不能稱為字串指標表。
- 直接尋找兩段字符表候選的完整 GBA ROM pointer 沒有得到可靠的 base pointer；
  這使「固定 pointer 直接指向字符表」尚未成立，但不排除透過結構偏移、壓縮
  解包或 runtime 初始化取得。

### 壓縮與 BIOS 呼叫假說

- 4-byte-aligned BIOS signature 初掃得到：LZ77 `8020`、Huffman `2774`、RLE
  `2805` 個候選。這些簽章在大型二進位 ROM 中高度容易誤命中。
- halfword-aligned `swi` 粗掃得到 LZ77 Wram `134`、LZ77 Vram `65`、Huffman
  `79`、RLE Wram `38`、RLE Vram `41` 個候選；它們只證明程式／資料中存在相同
  位元組形狀。
- 以 capstone 對 compression-related SWI 周邊做有限窗口反組譯後，只有部分候選
  能被乾淨解到 `svc`，且未完成參數資料流追蹤；目前**沒有文字專屬壓縮證據**。

## 2026-08-16：有界靜態 Shift-JIS 文字池

第二輪掃描不把全 ROM 的寬鬆候選當成腳本，而是以嚴格 NUL 結尾與可重讀條件掃描
`0x076000..0x082490`。工具：`tools/extract_sjis_strings.py`、
`tools/scan_sjis_regions.py`、`tools/scan_text_pointers.py`。

- 候選 source table：`2,325` 筆；輸出只在本機 ignored 檔案
  `research/super-robot-taisen-d-decoded.jsonl`。每筆以檔案 offset 作 `string_id`，
  `locale=ja`，並保留本機 provenance；不把日文原文或這個檔案提交到 Git。
- 這段資料依位址可觀察到 debug／駕駛員／機體／武器／UI／作戰目的／開場摘要／
  staff 等群組。這是內容形狀與分區線索，不是完整故事腳本覆蓋率證明。
- `tools/verify_sjis_source_table.py` 可逐筆從 clean ROM 找 NUL、嚴格解碼並比對
  本機 source table；目前預期 `2325/2325` 通過。驗證器不輸出原文。
- 以絕對 GBA ROM 位址掃描同一範圍：`4,947` 個 4-byte 對齊命中、`195` 個連續
  群組，其中 `4,137` 個命中正好對應本機 source table 的字串 offset。較大的群組位於
  reference offset `0x0a7ff0`（242 words）、`0x118fc0`
  （196）、`0x0ad690`（90）、`0x0b02a4`（87）、`0x118d24`（75）、`0x09152c`
  （62）。這些命中實際落在文字池範圍，足以支持「有界文字池＋pointer 結構」
  的靜態假說；尚未完成 caller／ID 語意／runtime renderer 驗證。
- `0x082400` 之後開始出現 metadata／其他二進位形狀；`0x082478..0x08248c` 附近
  可見 debug／日期類資料，因此 `0x082490` 是目前的**暫定**文字池終點，不是
  已證明的全遊戲 script end。
- 這個池內目前沒有辨識出自訂控制 byte 的可靠樣本；可見的 `%` 格式佔位與固定
  寬度資料在後續翻譯／回插時必須保留。控制碼、換行、說話者、行寬仍未定義。

這一輪的結論是：**標準 Shift-JIS 已對有界靜態池確認，但尚未對整個遊戲文本
確認；劇情／戰鬥對話與可逆回插仍未證明。**

## 2026-08-16：bounded mGBA runtime 邊界證據

本輪只做一個 session-local 的 mGBA 0.10.5 GDB 檢查；沒有把 port rewrite 或
啟動器基礎設施放進遊戲目錄。這次改用 main commit `0455796` 的共用
`core/gba/capture_runtime.py`、`core/gba/gdbstub_client.py` 與
`core/gba/render_vram.py`；本目錄既有的 `tools/gdbstub_client.py` 與
`tools/runtime_memory_probe.py` 保留作前一輪歷史證據，不再擴寫。

共用工具測試：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s core/gba/test -v`
通過 `6/6`。標準 capture 的 runtime I/O 為 `DISPCNT=0x1f00`、
`BG0CNT=0x0004`、`BG1CNT=0x0205`、`BG2CNT=0x0406`、`BG3CNT=0x0607`；
使用對應 charblock／screenblock 以 `render_vram.py` 重建後，BG3 可見 Banpresto
開場標誌。這是共用 I/O 解讀與圖形 renderer 的陽性證據，不是文字／字型證據。
capture 的 raw dump 與 PPM／PNG 只留在 `/private/tmp`，不進 Git。

| 檢查 | 結果 | 可支持的結論 | 明確限制 |
| --- | --- | --- | --- |
| ROM entry breakpoint `Z1,080000c0,4` | 共用 `capture_runtime.py` 得 `S05k`；`pc=0x080000c0`、`lr=0x08000000` | emulated CPU 確實進入 A6SJ ROM reset code | 不是文字或字型 renderer 命中 |
| VRAM write watchpoint `Z2,06000000,4` | 共用 `capture_runtime.py` 得 `T05watch:06000000;`；停止點 `pc=0x00000264`，`r1=0x06000000` | runtime 確實觸發一個寫入 VRAM 的圖形 transfer 邊界 | 只能作 graphics consumer 陽性證據；尚未證明來源是字型 |
| 靜態池首字 read watchpoint `Z3,08076000,4` | 共用 `gdbstub_client.py` bounded `10 s` timeout，隨後 interrupt 得 `S02`；`hit=false` | 在這個 boot window 沒有讀取池首 4 bytes | 不能推論整個池或其他字串沒有被讀取 |

上表的第一、二列是 runtime 陽性邊界，第三個有效檢查是文字池首字的 bounded 陰性
結果；它們合在一起只證明「ROM 執行到圖形初始化／transfer，且該時窗未讀池首」，
不證明文字 renderer、decoder、glyph addressing 或 glyph identity。這個里程碑因此
定名為**靜態文字池／實際 pointer／bounded runtime 邊界**，不是文字消費者已完成。
本輪停止擴張 runtime port 基礎設施；後續若需要，應先以反組譯與 pointer caller
分類縮小 renderer 候選，再開新的獨立 session。

## 2026-08-16：M1.5 bounded pointer caller／text consumer

### Pointer 所在位置分類

新增遊戲專屬工具 `tools/classify_pointer_callers.py`，只在指定 code range
反組譯 ARM／Thumb PC-relative literal load，並把 literal slot 與有界文字池內的
連續絕對 pointer run 交叉分類。實際重跑命令如下；JSON 報告只放 ignored 的
`work/`，不含解碼原文：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/classify_pointer_callers.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --target-start 0x76000 --target-end 0x82490 \
  --code-start 0x100 --code-end 0x76000 \
  --minimum-pointer-run 4 \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --top 20 \
  --json-output games/super-robot-taisen-d/work/pointer-caller-report.json
```

結果為 `4,947` 個 aligned pointer reference、`195` 個 pointer run、`915` 個
Thumb literal candidate；literal slot 分成 `652` 個普通 `literal_pool` 與 `263`
個 `pointer_table_member`，信心分數為 high `495`、medium `327`、low `93`，其中
`609` 個 target offset 正好是 source table record。這是 bounded caller 的分類
統計，不把分數當成 runtime reachability。

高信度反組譯確認 `0x0762d0`、`0x0763c4`、`0x07683c` 是指向同一有界資料區的
pointer table，不是直接的日文 source record。`0x08006b48`／`0x08006f10` 會把
這些表格指向的資料以 `0x080075e30` bounded copy helper 複製到 stack；其 caller
鏈為 `0x08007b7a -> 0x08006f10 -> 0x08006b48 -> 0x080075e30`。`0x08007b2a`
讀取 `0x03003380` 的 dispatcher byte，只有值在 `0..7` 才進 jump table；值為
`3` 時選到 `0x08007b7a` 這條 pointer-table path。這是目前可交付的精確觸發
條件。對 reset 後 30 秒 bounded window 設 `0x080075e30` breakpoint 沒有命中，
因此未把它宣稱為 boot/title consumer。

另一條直接 source-record 路徑在 `0x0800f474`：literal load 後以
`0x08007e04` NUL／bounded byte-copy helper 消費。共用 core GDB client 的正向
capture 命中 callsite `0x0800f49a`：

| 欄位 | runtime 值 |
| --- | --- |
| consumer entry | `pc=0x08007e04` |
| caller return／callsite | `lr=0x0800f49f`／`BL` at `0x0800f49a` |
| source | `r1=0x0807b3fc`（有界 source record） |
| destination | `r0=0x02000d60`（EWRAM buffer） |
| maximum length | `r2=0x10` |
| stop | `S05k` |

這組資料證明了至少一個實際 byte consumer、caller、LR 與 transient buffer；在
同一次 copy 後對 `0x02000d60` 做 30 秒 read watchpoint 沒有命中，該結果只限於
這個 buffer／時窗，不能否定後續其他 consumer。

### Glyph／codepage consumer

`0x08008724` 是比低階 tilemap helper 更高信度的文字 consumer。它逐 byte 判斷
單／雙位元組記錄，雙位元組與單位元組路徑分別在 `0x0800880c`／`0x080088bc`
呼叫 `0x080085fc`。後者讀取 16-bit code unit 與 mode flag，對 lead/trail byte
做 bounded arithmetic，返回 glyph offset；這是 code-unit 到 glyph addressing
的實際轉換，不把 offset 直接當作字元身分。窄字路徑再從 runtime slot
`0x020131d0` 取 glyph base，於 `0x080088c8` 完成 base+offset，最後呼叫
`0x08008650` 將 tile value 寫入目的 tile buffer；寬字路徑對應 runtime slot
`0x020103ac`。`0x08008650` 的 `strh` index 由 row／column／stack 參數組成，
因此不是單純的資料複製。

已確認的靜態 caller／trigger：

- `0x08008e04` 逐一掃描最多 `0x3c` 個 runtime queue entry；entry pointer
  `r5` 非零時，`0x08008e1c` 以 `r0=r5+8`、`r1=[r5+4]`、`r2=[r5+0x46]`、
  `r3=[r5]`、stack fifth argument `1` 呼叫 `0x08008724`。這是文字 queue 被
  消費的精確條件。
- `0x08066050`、`0x08066062` 是另一個雙 buffer UI routine 的兩個直接 callsite；
  `0x0806e01c` 則從另一個 runtime object 取 input buffer 後呼叫同一 consumer。
- `0x0800869e` 是 object 建立路徑在 fifth argument 為 zero 時的直接分支；
  `0x08008e1c` 是 queue drain 路徑。這些 callsite 都比單獨的 pointer literal
  更接近實際文字消費，但仍需由實際畫面／狀態觸發才能取得自然 runtime hit。

runtime 以同一個 session-local mGBA、共用 `core/gba/gdbstub_client.py` 做一次
受控驗證：先讓 ROM 初始化約一秒，於 EWRAM 寫入不提交的 Thumb trampoline，再
由 ARM `bx` 轉入 `0x08008724`；沒有修改 ROM。以 `0x0807b3fc` 作為 source pointer
並在 consumer entry 設 breakpoint 得到：

| 停止點 | 觀察 |
| --- | --- |
| `0x080085fc` | `pc=0x080085fc`、`lr=0x080088c1`（callsite `0x080088bc`）、`r0=0x8983`、`r1=1`；`r5=0x0807b3fc` 保留 source buffer |
| `0x080088c8` | `r4=0x1500`、`r0=0x1500`，即窄字 glyph base + codepage offset 的算術結果 |
| `0x08008650` | `pc=0x08008650`、`lr=0x08008919`（tile-write callsite `0x08008914`）、`r0=0x02019010`（tile buffer） |

這個 controlled trace 已證明 codepage lookup 與 glyph-address arithmetic 的
可執行路徑，也證明 tile buffer consumer；但該初始化時點的窄字 glyph-base slot
`[0x020131d0]` 仍為 zero，所以 `0x1500` 不是可接受的字型來源 identity 證據。
自然 reset／title 20 秒 window 對 `0x08008724` 沒有命中；目前可審核的結論是
「consumer 與精確 queue／dispatcher 觸發條件已定位，glyph addressing 已定位，
font resource initialization 與 glyph identity 尚未完成」，不是翻譯或字型回插
已完成。

### M1.5 結論

| 問題 | 狀態 |
| --- | --- |
| pointer table／literal pool 分類 | 已確認；tool report 給出 4,947／195／915 分類統計 |
| 真實 source byte consumer | 已確認；`0x0800f49a -> 0x08007e04` runtime positive |
| caller／LR／buffer | 已確認；`0x0800f49a`、`0x0800f49f`、`0x0807b3fc`、`0x02000d60` |
| codepage lookup | 已確認；`0x080085fc`，受控 runtime `r0=0x8983`、`r1=1` |
| glyph addressing | 已確認；`0x080088c8` base+offset、`0x08008650` tile write |
| font base initialization／glyph identity | 未確認；窄字 slot 在受控初始化時點為 zero |
| 自然 boot/title reachability | 未命中；精確 queue／dispatcher trigger 已記錄 |
| 翻譯／可逆回插 | 尚未開始／未證明 |

## 2026-08-16：M1.6 font resource initialization／glyph identity

本輪把 runtime 偵察限制在兩個已知 live font-base slot 與一條已確認的文字
consumer。沒有再做全域 pointer 掃描，也沒有把 ROM、完整日文 source、raw dump、
圖片或 mGBA work output 放進 Git。遊戲專用工具是
`tools/probe_font_resource.py` 與 `tools/build_m16_cohort.py`；純測試在
`tools/test_probe_font_resource.py`、`tools/test_build_m16_cohort.py`。

### Static resource path

`0x080083a0` 的 initializer 在 `0x08008450`／`0x0800845e` 以
`r0=0`、`r1=3`／`r1=2` 呼叫 `0x08003290`。resolver 讀取 literal table
`0x08081e58`，其 group-0 descriptor root 為 `0x081196b8`，再以 relative
descriptor entry 得到：

| slot | resolver index | descriptor relative | ROM resource pointer | 0x100-byte SHA-256 |
| --- | ---: | ---: | --- | --- |
| narrow `0x020131d0` | 3 | `0x00035fac` | `0x0814f664` | `9ea4cc823cda13f0bb5b717346a904eb822c641f998f88cf76a0b865d0ae0a09` |
| wide `0x020103ac` | 2 | `0x00007704` | `0x08120dbc` | `f9f4665a91cef443dd7e61eb588abb05c50f87c48217c49b91236d01d6475e71` |

這條已知初始化路徑的 resource pointer 直接落在 GBA ROM mapping；本輪 live
read 與 static descriptor 一致，沒有觀察到解壓或 RAM copy。這只限於這兩個
resource 與這條 initializer，不擴張成全遊戲沒有其他字型路徑的結論。

`0x08014e84` 的既有 Thumb caller setup 以 `r0=0x06000000`、`r1=0x06008000`、
`r2=0x0a` 呼叫 initializer，callsite 是 `0x08014e8c`。因自然 reset／title
window 與先前 bounded input poll 沒有到達該 caller，本輪使用 ROM 內既有 ARM
`BX` at `0x08000210` 進入 `0x08014e84`；initializer phase 沒有寫入 ROM 或
RAM code。mGBA 使用獨立 port `24567` 與 `skipBios=1`，因本機 session 沒有
官方 BIOS image；這是 runtime setup 限制，並非遊戲初始化已自然觸發的宣稱。

### Live slot watchpoints

一次性 session 先設兩個 write watchpoint，再由上面的已驗證 caller 執行；entry
停在 `pc=0x080083a0`、`lr=0x08014e91`，由 Thumb `BL` return address 還原出的
caller callsite 為 `0x08014e8c`。

| slot | watch stop PC | writer instruction | writer LR | live `r0`／slot value | live region |
| --- | --- | --- | --- | --- | --- |
| `0x020131d0` | `0x08008458` | `0x08008456` (`str r0,[r1]`) | `0x08008455` | `0x0814f664` | ROM |
| `0x020103ac` | `0x08008464` | `0x08008462` (`str r0,[r4]`) | `0x08008463` | `0x08120dbc` | ROM |

兩個 slot 在同一流程結束時均為 nonzero；watchpoint event 也讀回 resource bytes
並得到上表相同的 hash。這是本輪的 font resource initialization proof。

### First glyph identity chains

只有在兩個 slot 都已讀回 nonzero 後，probe 才會以 guard 放行對既有
`0x08008724` consumer 的 bounded temporary EWRAM stack／tile buffer setup。每個
identity 同時保留 strict source record 的 `string_id`／source hash、runtime
source pointer、code unit、codepage lookup、base+offset glyph bytes hash 與
tile writer output hash；Unicode 身分與 glyph addressing 分開記錄。

| source context | strict source hash | code unit → Unicode | mode | base slot/value + glyph offset | glyph pointer／bytes SHA-256 | tile writer／output SHA-256 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x0807b3fc` (`string_id=0x0007b3fc`) | `74130c92f0ed276e207ef1a1f09c683e146e0b282de1735e25421753b6b9d41e` | `0x8983` → `ラ` | 1 | `0x020131d0` / `0x0814f664` + `0x1500` | `0x08150b64`, 12 bytes, `55b2fd73918c81d6dd243d2268a88c5bd6f3d017b300e6820153c73e561b7838` | `0x08008650` via `0x08008914`; output `0x02019520`, 128 bytes, `0b24283a864c99088c88f548b98589932bccaba8fda4678d2103a533fe79eb7a` |
| `0x0807b380` (`string_id=0x0007b380`) | `7d3b523577ed1641eca7493db0ad72576d17665be8df9180450c6fa66eb3f381` | `0xda88` → `移` | 0 | `0x020103ac` / `0x08120dbc` + `0x5bea` | `0x081269a6`, 24 bytes, `14b957c056e66cdd282857d73cfa04df932fa7dcaaec7e4a9c026c24c8323515` | `0x08008650` via `0x0800886c`; output `0x02019670`, 128 bytes, `792e708f8ad7664b5614b4c1067191740108214107b683ed3c8a65265c90e868` |

兩條 chain 的 codepage lookup 都在 `0x080085fc`；窄字 callsite 是
`0x080088bc`，glyph base+offset 完成於 `0x080088c8`；寬字 callsite 是
`0x0800880c`，對應 base+offset 完成於 `0x08008818`。兩個 glyph byte window
與實際 tile writer output 都有 nonzero bytes。這些條件共同支持「source context
的 code unit 身分」與「runtime glyph address」的一致性，不以孤立 OCR 或字符表
順序推定 Unicode。

tracked 的最小 map 是 [`m16-glyph-provenance.json`](m16-glyph-provenance.json)，
只存上列 hash／address／count metadata 與兩個必要的單字元 identity；完整 source
仍在 ignored `research/super-robot-taisen-d-decoded.jsonl`。以中心
`0x0007b3fc` 建立的 16-record cohort 也只在 ignored
`work/m16-source-cohort.jsonl`，每筆保存 stable `string_id`、source hash、
control-token position 與 bounded pointer/caller provenance；中心 record 延續
M1.5 的 `0x0800f49a -> 0x08007e04` direct-copy positive，其餘沒有 runtime 命中
的 row 維持 static-only 或 provisional。

### Reproduction and boundary

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/verify_sjis_source_table.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --start 0x76000 --end 0x82490 --expected-count 2325

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/build_m16_cohort.py \
  games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --pointer-report games/super-robot-taisen-d/work/pointer-caller-report.json \
  --size 16 --output games/super-robot-taisen-d/work/m16-source-cohort.jsonl

PYTHONDONTWRITEBYTECODE=1 python3 \
  games/super-robot-taisen-d/tools/probe_font_resource.py \
  games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba \
  --port 24567 \
  --source-table games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl \
  --consumer-hijack --output games/super-robot-taisen-d/work/m16-font-runtime.json
```

最後一個命令需由本 session 自己啟動的 mGBA 執行：
`mGBA -C gdb.port=24567 -C skipBios=1 -g <A6SJ ROM>`。probe 的 post-init
temporary writes 只在兩個 slot nonzero guard 後發生；若自然畫面／queue 沒有
命中，不能把 controlled capture 擴張成完整場景覆蓋。M1.6 尚未處理控制碼與
layout 邊界、zh-TW 字寬／容量、encoder／回插與 round-trip；翻譯仍未開始。

## 2026-08-16：M1.7 bounded layout boundary／fail-closed no-op POC

本輪停止廣泛 pointer 掃描，只使用已確認的 `0x08008724` consumer、A6SJ
source table 與 M1.6 的兩個 resource base。工具為
`tools/m17_layout.py`、`tools/m17_poc.py` 及其純測試；tracked metadata 為
[`m17-layout-boundary.json`](m17-layout-boundary.json) 與
[`m17-poc-contract.json`](m17-poc-contract.json)。ROM、完整日文 source、raw
dump、圖片與 `work/` 報告都沒有進入 Git。

### `0x08008724` consumer 的靜態分類

以 A6SJ ROM 的 consumer code window `0x08008724..0x08008a0c` 做 bounded
Capstone 反組譯，window SHA-256 為
`b318d2b6e3dda2242397c61e2f9519114d7d898fe33c5475c93c99fa31abb613`。可直接
支持的分類如下：

| 類別 | 靜態證據 | 本輪名稱／策略 |
| --- | --- | --- |
| 終止 | `0x0800876c` load、`0x0800876e` compare、`0x08008770` branch to `0x08008798`；loop path 為 `0x08008950`／`0x08008952`／`0x08008954` to `0x08008958` | 只命名為 NUL terminator |
| 單位元組 glyph | consumer 以 `ldrh` 讀取 code unit、每輪 `adds r5, #2`；沒有獨立 single-byte glyph branch | 未證明為 glyph；ASCII／odd tail 維持 opaque，POC 拒絕 |
| 窄 glyph | `0x0800877a` 的低位元組 compare；`<= 0x87` 走 mode 1；`0x080088bc` lookup、`0x080088c8` base+offset | layout width 8、payload 12 bytes、address stride 12；base slot `0x020131d0` |
| 寬 glyph | 同一分流的 `> 0x87` path；`0x0800880c` lookup、`0x08008818` base+offset | layout width 12、payload 24 bytes、address stride 26；base slot `0x020103ac` |
| tile consumer | 兩條 glyph path 都呼叫 `0x08008650` | 已確認 writer target，不把 tile bytes當 Unicode identity |
| newline | consumer window 沒有 LF／CR 專用 branch；source corpus 也沒有 raw LF／CR | `unconfirmed_opaque`，翻譯 POC 拒絕 |
| 非文字／未知 | corpus 中 ASCII／format-like pair 與未對齊尾 byte 沒有已證明語意 | `opaque_ascii_or_format`／`opaque_unaligned_tail`，不憑數值命名；除 no-op 外拒絕 |

`0x080085fc` 的 codepage arithmetic 只用來產生 lookup offset；本輪沒有把
code unit 數值命名成控制碼，也沒有由 glyph 圖形或 slot 佔用推 Unicode 身分。
source cursor 每個 consumer unit 前進 2 bytes；因此本 consumer 只有已證明的
two-byte glyph unit 分流，沒有已證明的 single-byte glyph path。NUL 是目前唯一
已證明的 record 終止條件，並不等於所有未定位文本都採用同一格式。

### Corpus 與 bounded cohort

對 ignored source table 做 strict byte reread 與 metadata-only tokenization：

| 項目 | 結果 |
| --- | ---: |
| source records／strict ROM match | `2325`／`2325` |
| source corpus digest | `53a6d1d0d17ccb93a5cf9684d3e807d229bd3f87e76f619ffe16d767a176cc87` |
| NUL terminators | `2325` |
| tokenization → encode no-op byte identity | full corpus `2325/2325`；16-record cohort `16/16` |
| `glyph_only` records | `2189` |
| `opaque_or_unaligned` records | `136` |
| glyph units | `15885`（narrow `11902`、wide `3983`）|
| opaque ASCII／format-like units | `1032` |
| opaque unaligned tails | `88` |
| glyph-only line width range | `8..240`，56 種 width |

16-record cohort 以 `0x0807b3fc` 為中心，僅保存 stable string ID、offset、source
hash、長度、token／width count 與 no-op hash；不保存原文。POC 所選的兩筆皆為
10-byte payload、含一個 NUL terminator：

| string ID／source offset | source hash | width | token signature |
| --- | --- | ---: | --- |
| `0x0007b380`／`0x0807b380` | `7d3b523577ed1641eca7493db0ad72576d17665be8df9180450c6fa66eb3f381` | 56 | wide×4、narrow×1 |
| `0x0007b3fc`／`0x0807b3fc` | `74130c92f0ed276e207ef1a1f09c683e146e0b282de1735e25421753b6b9d41e` | 40 | narrow×5 |

兩筆都通過 `tokenization → encode` no-op，含 NUL 的 output 與 source
byte-identical；這是編碼器邊界測試，不是翻譯輸出或回插成功證明。

### Font resource occupancy 與保守容量

由 M1.6 descriptor root `0x081196b8` 的 resource boundaries 計算實體 slot，
再以 source codepage lookup 的 address formula 統計參照。空白 slot 只代表 bytes
為零，不能代表可分配的 Unicode 字元：

| resource | ROM range | payload／stride | physical／addressable | referenced | blank／unreachable | conservative new capacity |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| narrow (`0x020131d0`) | `0x0814f664..0x08150fe4` | 12／12 | 544／544 | 257 slots、11902 occurrences | blank 168；blank referenced 3；unreachable 0 | 165 narrow slots upper bound |
| wide (`0x020103ac`) | `0x08120dbc..0x0814f664` | 24／26 | 7332／6580 | 743 slots、3983 occurrences | blank 0；unreachable 752 | 0 |

因此本輪對 zh-TW CJK／寬字採保守容量 0；窄字 165 只是未證明 encoder 與
語意前的 slot upper bound，不能當成可直接翻譯的字元表容量。resource pointer
本身是 M1.6 live initialized ROM base；本輪沒有再靜態假設 RAM-only pointer，
也沒有新增 resource copy／解壓路徑宣稱。

### Fail-closed POC 契約

`tools/m17_poc.py` 只對上列兩筆 source record 建立 contract，沒有修改 ROM，
沒有建立 translation ledger。候選必須保留原始 source hash，且必須同時滿足：

- exact control／token signature；opaque token、newline candidate、glyph class
  mismatch 或 unaligned record 一律拒絕；
- exact source line width 且不得 overflow；
- 所需 glyph slot 不得缺字，新增 slot 不得超過保守容量；
- candidate payload length 必須與 source length 相同；
- source hash、控制 token、行寬、缺字、容量或長度任一不符即 fail-closed。

兩筆結果均為 `accepted=true`、`byte_identical=true`，其 payload length 都是 10；
兩份完整 metadata 與 rejection names 在 `m17-poc-contract.json`。這只是可逆
POC 的輸入契約與 no-op round-trip 前置條件，尚未實作 zh-TW encoder、glyph
allocation 或 ROM reinsert。

### Runtime boundary 與下一個缺口

本輪沒有新增 mGBA runtime capture：M1.6 已提供 initialized slot、consumer 與
tile-writer 的 controlled proof；對 M1.7 的 token／capacity／no-op 邊界，靜態
consumer 與 source-safe hash 已足夠，避免把 controlled layout 或 zero-base
trampoline 誤報成自然畫面證據。自然 menu／queue 的 newline、layout break、
說話者／分支控制仍未達到可審核條件。

下一步必須先補齊：newline／opaque token 的實際 runtime 語意、完整行數／行寬
與 record boundary、zh-TW codepoint 到 glyph slot 的合法 encoder／缺字策略、
以及 rebuilt ROM 重抽取與 byte-level round-trip。未完成前不開始批量翻譯。

## 2026-08-16：M1.8 narrow allocator／static zh-TW POC

本輪只處理窄字 resource，沒有建立或使用任何寬字新 slot。先由 ignored
source table 選一筆全窄、無專名、兩個 code unit 的短 UI record（stable
`string_id=526424`、ROM address `0x08080858`）；tracked 文件只保存 raw／ledger
source hash，不保存日文原文。翻譯工作確實依序經過 `seed ledger → restore_translations.rb`
→ ignored work → `strip_translations.rb`，唯一 tracked 翻譯檔為
[`translations/m18-static-poc.jsonl`](../translations/m18-static-poc.jsonl)。

### Narrow formula、range 與 occupancy gate

對 `0x080085fc` 的 A6SJ Thumb code 做 direct disassembly，mode 1 的運算為：

```text
lead = code_unit & 0xff
trail = (code_unit >> 8) & 0xff
lead' = lead-0x43 if lead > 0xdf
        lead-3    if lead > 0x87
        lead      otherwise
row = lead' - 0x81
trail' = trail-1 if trail & 0x80 else trail
slot_index = ((row * 3) << 6) - 0x40 + trail' - row * 4
byte_offset = slot_index * 12
```

窄字 resource 是 `0x0814f664..0x08150fe4`，544 個 physical／addressable slot，
所以在本 resource 大小下可安全定址的 raw code-unit range 是：lead `0x81..0x82`
搭配 trail `0x40..0x7e` 或 `0x80..0xfc`，以及 lead `0x83` 搭配 trail
`0x40..0x7e` 或 `0x80..0xe8`；第一個 raw pair 是 `8140`，最後一個是 `83e8`。
544 個 slot 均只有一個 code-unit mapping，沒有 formula collision。

以完整已驗證 corpus 重算 occupancy：257 個 slot／11,902 次引用、168 個空白
physical slot，其中 `0/57/58` 是 blank-but-referenced，固定保護；剩下 165 個
才是 addressable 且未被 corpus 引用的可分配候選。allocator 使用高端空槽，這次
配置 slot `543`／`542`，raw code unit 為 `83e8`／`83e7`，沒有覆寫保護 slot，
也沒有觸碰 wide resource（容量仍為 0）。完整 metadata 在
[`research/m18-narrow-poc.json`](m18-narrow-poc.json)。

### 12-byte glyph format 與固定字型來源

`0x080085b0` 的窄字 renderer 逐列讀取 12 bytes；每 byte 是 8 pixels、MSB 為
左側像素，因此格式是 8×12、1bpp。renderer 將每兩個 bit 轉成一個 4bpp byte，
偶數 pixel 放 low nibble、奇數 pixel 放 high nibble；`0x08008650` 只負責按
tile-row／column offset 寫 halfword。已用既有 `ラ` resource bytes hash 與靜態
4bpp render hash 交叉驗證此 packing，沒有由圖形猜 Unicode identity。

本輪固定使用 repo 已核准的 GNU Unifont T-source 17.0.05：
`vendor/fonts/unifont/unifont_t-17.0.05.hex.gz`，SHA-256
`c1768bd7fea203db1f419045d5a9e4d420772445e29b96c8873471d3f46c5b53`；授權檔
`OFL-1.1.txt` SHA-256 `869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded`，
依 SIL OFL 1.1／GPL font exception 可再分發。衍生器固定採 16×16 box-any
downsample 到 8×12；這是本輪 static POC 的明確實驗轉換，不宣稱最終字型美術品質。

### Fail-closed allocator 與 static POC

allocator 的拒絕條件固定為 ROM／font／license hash mismatch、source hash
mismatch、code-unit／slot collision、range outside、wide glyph、opaque/control、
missing glyph、capacity exhausted 與 variable length。source record payload 是
4 bytes／2 narrow units／line width 16；`zh-TW` static target payload 也固定為
4 bytes／2 narrow units／width 16。配置的兩個 target glyph metadata 為：

| target codepoint | slot | raw code unit | glyph bytes SHA-256 | 4bpp render SHA-256 |
| --- | ---: | --- | --- | --- |
| `U+6c92` | 543 | `83e8` | `fc802795e0a087b4a040a4aa021aec11f1ce171562606996e46720d81261b74c` | `7ea2c7a3ca398e333fa6b701517e7964deabe4ce64f7dadf913e4bb135677b2c` |
| `U+6709` | 542 | `83e7` | `baec37d94010d471df77dae5d16aecd1d581178af6c0f65f1aabbfbde11ee01d` | `b5cd53c77777564920183a17e99524d08081b21e69da1e20870a05c702ed2078` |

static render／hash gate 顯示 target changed record 的 8×12 1bpp hash 為
`d9afb0558337ac6763bd136ad0622a13a29bcd30924b9518e56b3a9bfed00d97`、4bpp hash
為 `69aa6186e6fafeb3c3d5e96ad4031ba0f80f0d595526f4f9e01b45dcd6cc99e1`；相鄰
`0x08080860` record 的 1bpp／4bpp hashes 在 patched 前後均為
`20b2c971fdc3f2643de157bb542dd62f3658f40024d5c3502d6edfc80db89105`／
`c0ef81f33c1de225a8f8f7dced258c92641ed2b7daa1e62c7f2d173bfb99c54f`，
`adjacent_untouched=true`。

### ROM／BPS gate 與限制

static patched ROM 只改 28 bytes：target record 4 bytes，加上兩個窄字 slot 各
12 bytes。patched SHA-256 為
`b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce`，CRC32
`787fa8cc`。BPS 為 66 bytes、SHA-256
`4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31`，patch CRC32
`725f824b`；create/apply 後與 patched ROM byte-identical。ROM、BPS、render image
與 work record 全部留在 ignored `roms/`／`work/`。

本輪 runtime status 是 pending：static glyph render、target／相鄰 record re-read、
allocator gate 與 BPS round-trip 已通過，但尚未用獨立 mGBA session 顯示 patched
record。Unifont downsample 的字形風格、未定位 corpus 對新 code-unit 的潛在使用、
newline／完整 layout 與 full-game QA 仍是風險；這一筆 `ai_draft` 不代表完整翻譯
或自然畫面通過。

## 2026-08-16：M1.9 patched target runtime QA 邊界

M1.9 將範圍限制在 M1.8 唯一 translation ledger record `string_id=526424`、兩個
窄字 slot `543/542`，以及相鄰 untouched record `526432`。tracked 證據只保存
source／ledger hash、offset、長度、控制 token、slot、bytes／render hash；完整日文、
ROM、BPS、PGM 與 probe JSON 均留在 ignored `work/`。可重跑工具為
`tools/m19_runtime_qa.py`，其 GDB、initializer guard、consumer、codepage、glyph
addressing、tile-writer 與 self-render 分層輸出 metadata；純函式 gate 在
`tools/test_m19_runtime_qa.py`。

### Static gate（已通過）

| 項目 | 證據 |
| --- | --- |
| target source | ROM offset `0x080858`／address `0x08080858`；raw hash `d00ed112…`；ledger hash `868310e1…`；4-byte payload、2 units、line width 16、NUL、無已知 control token |
| patched target | payload hash `13b51fc2…`；同長；code units `0xE883`／`0xE783`；窄字 slots `543/542` |
| glyph static render | slot 543 bytes hash `fc802795…`、4bpp `7ea2c7a3…`；slot 542 bytes hash `baec37d9…`、4bpp `b5cd53c7…`；target 1bpp `d9afb055…`、4bpp `69aa6186…` |
| adjacent | offset `0x080860`／string `526432`；base／patched payload hash `b5635bbc…` 相同；1bpp `20b2c971…`、4bpp `c0ef81f3…` 相同 |
| ROM／BPS | base `12b706b6…`；patched `b58ef432…`；BPS 66 bytes／`4f694170…`；M1.8 create/apply byte-identical，本輪只重核 hash／artifact identity |

### Runtime 分欄與 negative evidence

M1.6 已有的 controlled positive 仍確認初始化與 consumer 的 call chain：font slots
`0x020131d0`／`0x020103ac` 分別寫入 nonzero ROM base `0x0814f664`／`0x08120dbc`，
並走 `0x08008724` → `0x080085fc` → `0x080088c8` → `0x08008650`。這能證明
consumer path 存在，但不把 M1.6 的 `ラ`／`移` sample 當成 M1.9 target 畫面。

本輪使用獨立 mGBA、port `24567`、每個 probe 一條 GDB connection。兩次 clean
restart 都只做一次明確命名的 `idle_boot` natural window；listener 曾可見於
`*:24567`，但 probe 在 target stop window 得到 `target did not stop before timeout`。
同一 single-connection 狀態後續握手沒有有效 packet response；依 GDB stub 的單連線
限制，不重用、不做第三次 clean restart。結果精確標記為 `transport_negative`：
M1.9 patched target 的 runtime screen、writer destination、cache／VRAM hash、
相鄰 runtime equal hash 均是 `not_observed`，不是 ROM／翻譯失敗，也不是自然不可達
的證明。完整欄位與 follow-up 條件在 [`m19-runtime-qa.json`](m19-runtime-qa.json)。

因此本輪只完成 static gate 與 transport boundary；下一個 runtime session 必須
用新的 mGBA process／port，先重做 base／patched controlled capture，再分開嘗試
自然 menu／queue。newline 仍只有 `0x08008724` 靜態「無獨立 newline branch」證據，
不得外推成完整引擎 newline 安全。

## 2026-08-16：M1.9 follow-up port 24731 transport boundary

依前輪要求只啟動本 session 自己的 mGBA，使用新的獨立 port `24731` 與 A6SJ base ROM。
launcher 成功，但未能形成 GDB runtime evidence：普通 probe 在 localhost socket 被
sandbox 以 `Operation not permitted` 拒絕；申請本機 socket 的 escalated probe 在
approval transport 階段中斷，未執行 probe。自己啟動的 mGBA 已清理停止，沒有重用其他
session 的 process／port，也沒有把這次 transport negative 解讀成 ROM／翻譯失敗。

因此 `research/m19-runtime-qa.json` 新增的 follow-up metadata 只記錄 port、啟動／
清理與 transport 結果；patched target、slot `543/542` writer／VRAM、screen layout、
NUL／newline runtime branch 均維持 `not_observed`／pending。

## 2026-08-16：M1.9 patched controlled retry／bounded runtime negative

在自己的 headless mGBA PID／port `2346` 上，以 M1.8 patched ROM（SHA-256
`b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce`）及既有 BPS
（SHA-256 `4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31`）做
一次 single-connection controlled consumer。font-base nonzero guard 通過，表示
這次確實走到已證明的初始化後 consumer setup；但 target `0x08080858` 的 static
NUL／兩窄字 contract 預期兩個 unit，runtime probe 只得到一個 codepage lookup 與
一個 narrow glyph event，於 `codepage=1/glyph=1/expected=2` fail-closed。沒有把
未完成 loop 當成 target render proof；writer destination、tile/cache hash 與 screen
均標為未捕捉。

同一 session 的下一次 bounded metadata trace 在 initializer 前收到 `S04`、
`PC=0x00000004`，也沒有產生 runtime evidence；兩個自己啟動的 process 都已停止，
沒有使用其他 session 的 ROM／process／port。這兩次結果寫入
`research/m19-runtime-qa.json` 的 `controlled_attempt_2346` 與 `trace_attempt_2346`，
只代表 runtime／startup negative，不代表 ROM 或譯文失敗；本切片不再增加 restart。

## 2026-08-16：M1.12 semantic/caller boundary

`tools/m112_semantic_caller_boundary.py` 只重用 ignored `pointer-caller-report.json`，
不重新做全 ROM pointer scan。它把 609 個 exact source candidates／370 個 source
records 依 function-start 分成 123 個 caller cohorts，完整 coverage 由 candidate／
record ID hash 保存，tracked report 只回傳前 32 個 bounded cohorts，並分列 300 個
無 function-start anchor 的 exact candidates。每 cohort 只保存 caller address、
literal/confidence、structural partition、following call-target count 與 hash，沒有
原文或完整 source table。

同一報告重讀 strict source／NUL／token shape 2325/2325，保留 939 narrow、833 mixed、
417 wide、136 opaque 的 structural boundary；M1.6 的 2 個 controlled runtime
positive 與 exact-pointer overlap（1 筆）分欄，natural caller／screen 仍
`not_observed`。story、branch、battle dialogue、unit/pilot/weapon/spirit、UI、
speaker、newline 與 engine width limit 全部 `unconfirmed`；wide existing-slot map
仍為 743 identities、runtime confirmed 1、新 wide capacity 0。這是分類邊界與下一個
runtime gate，不是語意分類或新增翻譯。

## 2026-08-16：M1.13 fail-closed narrow／wide encoder contract

本輪新增 [`tools/m113_full_encoder_contract.py`](../tools/m113_full_encoder_contract.py)，
不重新掃描 ROM，也不產生 target 或修改 ROM。它重用 ignored M4 narrow allocation 與
wide reuse audit，將可回插邊界收斂成一個可測的 encoder contract：窄字須通過固定 ROM、
Unifont source／license hash、code-unit→slot formula、codepoint／unit／slot collision
與固定長度；寬字只允許既有 map 中具 `runtime_confirmed_bounded` 的 identity。ledger
的 source hash 會重新對回 strict source table 的 UTF-8 identity，source payload 再對回
clean ROM；輸出只保存 hash、address、count、mode 與 gate metadata。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| source no-op | strict source 2325/2325；token encode no-op 2325/2325 |
| narrow map | 28 allocations；codepoint index hash `614ce93a…`；ROM／font／license hash gate 通過 |
| wide map | 743 existing identities；runtime-confirmed 1（`0xDA88`／slot 905）；static-only 742 |
| ledger | 12/12 source hash／encode accepted；same-length 12/12；encoded modes narrow 48 |
| reject boundary | static-only wide、wide new slot（capacity 0）、missing glyph、opaque/control、variable length、hash mismatch、collision |
| semantic status | `full_semantic_translation=false`；完整 story／branch／battle／unit／speaker／newline 仍未確認 |

這個 slice 證明的是「窄字 static subset＋一個已 runtime 確認的既有寬字 identity」的
可驗證 fail-closed encoder，不是 743 個 wide renderer proof，也不是完整翻譯或完整
resource expansion。完整輸出在 [`m113-full-encoder-contract.json`](m113-full-encoder-contract.json)；
ROM、font source、working／raw output 仍留 ignored。

## 2026-08-16：M1.14 patched consumer trace 的精確 negative

本輪沒有再做廣泛 pointer scan，也沒有新增翻譯。以自己的 patched M1.8 ROM、fresh mGBA
process、port `2346` 與單一 GDB connection 重跑 bounded metadata trace；ROM SHA-256
`b58ef432…` 與 BPS 對應的 patched artifact hash 已先核對，兩個 live font base
`0x0814F664`／`0x08120DBC` 的 nonzero guard 通過。原始 trace 留在 ignored `work/`，
tracked 摘要由 [`tools/m114_runtime_boundary.py`](../tools/m114_runtime_boundary.py)
只保留 address／code-unit／count／status。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| requested record | source offset `0x080858`／pointer `0x08080858`；expected 2 units |
| observed consumer event | pointer `0x02018368`；unit `0x628D`；codepage 1；narrow glyph 0；tile-writer event count 36 |
| argument gate | `consumer_argument_match=false`；`unit_loop_status=natural_or_unmatched_consumer` |
| raw completion | 有 raw glyph-complete event，但因 source pointer mismatch 不計入 target proof |
| target QA | writer destination／target tile cache hash `not_proven`；screen hash `not_observed`；ROM／翻譯失敗 `false` |
| next condition | 必須在 caller/callsite 或已驗證 callee entry 捕捉 requested pointer 與全部 unit，再做 writer／VRAM/layout QA |

這個 slice 修正了 runtime 工具的兩個安全問題：bounded stack seed 與 entry setup 對齊
既有 consumer helper，並要求 observed source pointer／unit count match 才能宣稱完成。它
沒有把另一個 runtime buffer 的 glyph output 偷換成 `string_id=526424` 畫面，也沒有解除
M1.9 target／自然 menu／newline branch 的 pending 狀態。

## 2026-08-16：M1.15 known consumer callsite boundary

本輪只針對已知的 `0x08008724` consumer 做 direct-reference audit，不重新掃描一般
pointer pool，也不替 register-indirect dispatch 猜 caller。工具
[`tools/m115_consumer_callsite_audit.py`](../tools/m115_consumer_callsite_audit.py) 對
`0x08000000..0x08076000` 的 bounded executable prefix 檢查 direct Thumb BL／BLX
immediate target 與 PC-relative literal target，並保存 executable-range hash；完整 source
與 raw bytes 不寫入 tracked report。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| bounded range | `0x08000000..0x08076000`；length `483328`；range SHA `2e302689…` |
| known target | consumer `0x08008724` |
| direct call candidates | Thumb BL／BLX `0`；PC-relative literal `0` |
| static conclusion | `runtime_caller_required=true`；register-indirect dispatch `unresolved` |
| runtime follow-up | `tools/m115_caller_probe.py` 只設 consumer entry breakpoint，預計記錄 LR／callsite／r0；本輪 approval transport 在 process 啟動前拒絕，未產生 runtime evidence |

這個 slice 只把「沒有可直接由 bounded static reference 得到 caller」證明清楚；它沒有
把 direct-call count 0 解讀成 consumer 不可達，也沒有解除 story／branch／battle／unit
語意、newline／speaker／最大寬度與自然畫面 pending。下一個安全入口是使用已授權且可用的
runtime transport 捕捉 entry LR／r0，再以該 caller 做受控 source queue／layout QA。

## 2026-08-16：M1.16 full-corpus layout-safe static contract

為了讓未證明的控制碼／版面不會被誤當成可翻譯容量，本輪新增
[`tools/m116_layout_safe_contract.py`](../tools/m116_layout_safe_contract.py)。它重讀完整
2325 筆 strict source，僅接受 NUL 終止、token encode no-op、glyph-only narrow、單行
且 observed width 不超過 64px 的 record。64px 是目前 static POC 的保守配置上限，不是
引擎最大行寬；工具不輸出 source text，也不替 opaque token 命名 newline／speaker／branch。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| source gate | strict 2325/2325；NUL 2325/2325；token encode no-op 2325/2325 |
| accepted static layout subset | 624 records；glyph-only narrow；single-line；width `<=64px`；ID hash `f8695cb6…` |
| rejected narrow | 315 records；narrow glyph-only 但 width over observed cap |
| other rejected partitions | mixed 833；wide 417；opaque／unaligned 136 |
| token metadata | glyph 15885；opaque ASCII／format-like 1032；unaligned tail 88；未命名語意 |
| policy | `max_lines=1`；newline／speaker／branch／variable length／wide new slot 皆 reject；`engine_width_limit_proven=false` |

這個 slice 是回插前的結構容量邊界，不是 624 筆翻譯完成、不是完整 encoder，也不能
把 64px 外的窄字直接判定為引擎不支援；下一步仍需 caller／自然畫面或明確 callee
state 證明實際 line layout，再決定是否能安全放寬 cap。

## 2026-08-16：M1.17 full-corpus pointer／caller coverage matrix

本輪只重用 ignored `work/pointer-caller-report.json` 與已提交的 M1.12 semantic report，
沒有重新掃描 pointer。`tools/m117_corpus_coverage.py` 先重讀 clean ROM／strict source
的 2325 筆 structural partition，再將 609 個 exact source candidates／370 個 records
按 partition 與 function-start cohort join；完整 join 由 ID／instruction／cohort hash
保存，tracked output 不含 source text。

### 可重現結果

| partition | total records | exact pointer records | exact occurrences | uncovered records |
| --- | ---: | ---: | ---: | ---: |
| glyph-only narrow | 939 | 83 | 180 | 856 |
| glyph-only mixed | 833 | 126 | 160 | 707 |
| glyph-only wide | 417 | 101 | 206 | 316 |
| opaque／unaligned | 136 | 60 | 63 | 76 |

全體 exact candidates 是 `609`、exact records `370`、caller cohorts `123`，其中
anchored candidates `309`、unanchored `300`；所有 candidate 都落入某個 cohort，
但 `natural_caller_status=not_observed`。story、branch、battle dialogue、
unit/pilot/weapon/spirit、UI 全部保持 `unconfirmed`；controlled runtime positive
只作 runtime evidence，不作語意標籤。

這個 matrix 補的是覆蓋缺口與下一個 caller work queue，不是話數／分支／戰鬥／機體語意
完成，也沒有解除 opaque／wide／newline／speaker／最大寬度的 fail-closed 邊界。

## 2026-08-16：M1.18 unified control／newline／branch／layout contract

本輪沒有重新做廣泛 pointer scan，也沒有修改 ROM。`tools/m118_control_layout_contract.py`
重用已驗證的 `0x08008724` consumer contract、strict source table 與 M1.16 layout-safe
摘要；它只輸出 instruction/function hash、offset／ID digest、token class、count 與 gate，
不把完整 source text 寫入 tracked report。

### 可重現結果

| gate／分類 | 結果 |
| --- | --- |
| source／NUL／token encode no-op | `2325/2325`、`2325/2325`、`2325/2325` |
| consumer grammar | NUL terminator；兩 byte narrow／wide glyph；其他 unit `opaque_and_reject` |
| glyph counts | narrow `11902`；wide `3983` |
| opaque counts | ASCII／format-like `1032`；unaligned tail `88` |
| observed width | `0..240px`；不是 engine maximum proof |
| layout-safe subset | `624` 筆 glyph-only narrow、single-line、observed width `<=64px` |

`0x08008724` 的 bounded disassembly gate 顯示沒有 dedicated newline branch；這只代表本輪
靜態 consumer window 的 branch 結構，不代表整個引擎沒有以其他 caller／script 方式換行。
newline、speaker、branch 語意與 engine width limit 仍標為 `unconfirmed`，unknown token
維持 opaque/reject；因此 M1.18 沒有新增翻譯，也沒有解除 mixed／wide／opaque 或變長
record 的 fail-closed 邊界。

本輪驗收：工具輸出標籤明確標成 `static_no_newline_branch`，M1.18 單元測試與完整本作
工具測試、core/gba、strict source、AST、ledger schema、repository safety 均需在 commit
前重跑並保存命令／結果。下一步回到自然或 controlled caller/callsite 的 runtime reroute，
並優先覆蓋 newline／speaker／branch／最大寬度與 story／battle／unit 分類；在沒有新語意
或畫面證據前不擴張 static UI 翻譯批次。

## 2026-08-16：M1.19 patched natural caller reroute

本輪先修正 M1.15 bounded known-target audit 的一個 under-scan：Capstone 從 ROM reset
entry 連續反組譯時，在前段 undecodable gap 停止，舊 report 的 direct `0` 不是完整
bounded range 結果。`tools/m115_consumer_callsite_audit.py` 現在只在原本相同的
`0x08000000..0x08076000` 範圍啟用 skipdata 跨 gap，重抽取結果為 direct Thumb
consumer candidate `5`、PC-relative literal `0`；這是 bounded candidate inventory，
不把所有 candidate 自動命名成劇情語意。

接著使用新鮮、自有的 headless mGBA PID `88376`、port `2346`、patched M1.8 ROM，
只建立一條 GDB connection，執行既有 `m115_caller_probe.py`。ROM SHA-256 為
`b58ef432…`，兩個 live font-base slot 都 nonzero；自然 window 在
`0x08008724` 停下，保存的 runtime metadata 為：

| 項目 | 結果 |
| --- | --- |
| LR／caller callsite | `0x08066055`／`0x08066050` |
| r0 source pointer | `0x02018368`，`ram_or_io` |
| target pointer | `0x08080858`，`target_pointer_match=false` |
| consumer arguments | `r1=0x06008400`、`r2=0x0D`、`r3=0x05`、stack arg 0=`1` |
| static setup | `r0<-r7`、`r1<-r5+0x400`、`r2=0x0D`、`r3=0x05`，bounded window hash verified |
| target／screen | target render、tile writer、VRAM／screen hash `not_proven` |

這條證據把「可達的自然 consumer caller」與「target source record」分開：已知 caller
是 RAM-buffer UI path，不是 `0x08080858` 的 target entry。`m119_caller_reroute.py`
只輸出 callsite／instruction hash、register/address metadata 與 gate；不保存 RAM
buffer、完整 source 或畫面。下一個 runtime 條件是取得 target caller/index 或 buffer
producer 的可審核來源，再進行一次受控 callee-entry／screen proof；在此之前不把
自然 hit 外推成 patched glyph QA，也不擴大翻譯批次。

## 2026-08-16：M1.10 record boundary／opaque-token audit

在不擴大 runtime 假說的前提下，`tools/m110_boundary_audit.py` 對 clean ROM 的
`0x076000..0x082490` 與 ignored strict Shift-JIS source table 做完整 2325 筆
逐筆 byte identity 檢查。工具只把 source text 留在本機記憶體，tracked 摘要只留
offset、hash、length、NUL、token count、class count、line-width 統計與 bounded
cohort metadata；可重跑輸出在 ignored `work/m110-boundary-audit.json`，tracked
摘要在 [`m110-boundary-audit.json`](m110-boundary-audit.json)。

### 已確認的 boundary／contract 分布

| 項目 | 結果 |
| --- | --- |
| source records | 2325；`0x08076000..0x08082490`；offset 嚴格遞增、duplicate 0、overlap 0 |
| terminator | 2325/2325 為 NUL；embedded NUL 0；最後 terminator `0x08082489` |
| ROM/source equality | 2325/2325 strict Shift-JIS bytes 相等 |
| tokenization | glyph-only 2189；opaque／unaligned 136；glyph 15885（narrow 11902、wide 3983） |
| opaque 分布 | ASCII／format-like opaque 1032 tokens；unaligned tail 88；未觀察到 newline candidate |
| layout | 可進 glyph contract 的 2189 筆，width 8..240、56 個 distinct width；最大值只是 corpus 統計，不是引擎最大行寬證明 |
| no-op | 全部 2325 筆 encode byte identity；其中 2189/2189 通過 glyph-only contract，136 筆 opaque／unaligned 明確拒絕翻譯 |

`0x08008724` 的 static consumer branch 仍只有 NUL exit、two-byte unit、narrow／wide
分流；沒有 dedicated newline branch。因此 `m110_boundary_audit.py` 將未知 pair、
unaligned tail 與任何 newline-looking data 保持 opaque，不以 byte value 命名語意，
也不把 `width=240` 外推為所有畫面的安全寬度。中心 `0x0807B3FC` 的 16-record
bounded cohort 為 16/16 no-op、16/16 contract-eligible；其 source-safe digest、
offset digest 與所有計數均在研究 JSON，沒有完整原文。

這個 slice 只收斂 record boundary、NUL 與 fail-closed token policy；speaker、
multi-line layout、分支腳本與實際 newline semantics 仍未完成，也沒有開始第二筆
翻譯或批量翻譯。

## 2026-08-16：M1.11 bounded layout contract

`tools/m111_layout_contract.py` 只反組譯已在 M1.5／M1.7 證明的
`0x08008724..0x08008A0C`，並以 instruction PC、branch target 與 function hash
做 fail-closed gate；沒有再做廣泛 pointer scan，也沒有執行 ROM 修改。摘要在
[`m111-layout-contract.json`](m111-layout-contract.json)，完整 disassembly 不進 Git。

已固定的 layout facts：

- `0x0800876c` `ldrb` → `0x0800876e` compare zero → `0x08008770` NUL exit，
  render loop 另有 `0x08008950`／`0x08008954` NUL exit；source cursor 每一輪
  `0x08008774` `ldrh` 後在 `0x0800878c` 前進 2 bytes。
- low byte `<=0x87` 走 narrow width 8，否則走 wide width 12；像素寬累積在 `sl`，
  tile columns 是 `ceil(width/8)`，partial flag 是 `width & 7 != 0`，allocation
  unit 64 bytes、tile row 32 bytes、glyph render 12 rows。
- 結尾 mode field 在 `0x08008968` sign-extend 後於 `0x0800896c` 比較 1；等於 1
  走 bounded direct destination-copy path，其他值到 `0x080089c6` helper path。
  這是 branch boundary，不是 speaker、newline 或劇情 mode 的語意命名。
- 在 2325 筆 corpus 的 glyph-only subset，觀察 width 8..240、56 種值，最大觀察
  30 columns／1920 bytes；這是 corpus upper bound，不是 engine hard limit。

因此 M1.11 完成 NUL／unit／width／tile allocation 的靜態 contract，但 newline、
speaker、mode branch meaning、完整 multi-line、script branch 與自然 runtime layout
仍未證明；unknown token 仍 fail-closed opaque，翻譯範圍沒有擴大。

## 2026-08-16：M2 bounded zh-TW glossary provenance

本輪只建立術語準備資料，不開始第二筆或批量翻譯。追蹤檔
[`../translations/glossary.zh-TW.tsv`](../translations/glossary.zh-TW.tsv) 不保存日文
原文；每列只保存 semantic `term_key`、zh-TW 候選、分類、狀態、source record ID、
Shift-JIS raw SHA-256、公開來源 URL 與決策說明。`tools/m2_glossary_audit.py` 從本機
ignored `research/super-robot-taisen-d-decoded.jsonl` 讀取 source text 並只比較 hash，
不把 text 寫入 report 或 stdout。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| glossary entries | 17；accepted 12、deferred conflict 4、provisional 1 |
| categories | character 4、unit 5、ship 1、spirit 5、system 2 |
| source table | 2325 records；18 個 distinct referenced records |
| source provenance | 18/18 raw Shift-JIS hash matches；source text emitted `false` |
| fail-closed | deferred entries 不帶 `zh_tw`；accepted／provisional 至少兩個 HTTPS sources |
| test coverage | real glossary、hash mismatch、kana leak、single source、deferred target gate |

機體名稱以臺灣維基與 RoboInfo D／機體頁的共同用法為優先；格拉基耶斯另有巴哈姆特
D 討論佐證；精神指令以兩個巴哈姆特資料頁交叉。約修／莉姆在短名／全名之間、阿姆羅
在臺灣維基／巴哈姆特用法之間、拉・凱拉姆在中點字元之間仍有差異，4 列維持
`deferred_conflict`，不得被後續翻譯工具當成已批准 target。相關來源 URL 與逐列
採用理由保存在 TSV；摘要與衝突 key 只在 [`m2-glossary-audit.json`](m2-glossary-audit.json)。

這個 slice 證明的是「術語資料可追溯且 source-safe」，不是字寬、Unicode glyph capacity、
控制碼安全、翻譯品質或 ROM 回插已完成。下一輪仍須先選擇可達且 glyph-only 的小批次，
以 restore／working／strip 做 ledger，並在每筆 target 建立 width、slot collision、
control token 與 no-op／round-trip gate。

## 2026-08-16：M2 batch-1 bounded UI target

M2 第一筆新 `ai_draft` 只選 source record `string_id=526432`，因為它是已確認的
兩窄字、NUL 終止、16px line width、無 control token record；相鄰 `526424` 留作
untouched 對照。流程確實依序執行 `m18_narrow_allocator.py seed-ledger`、
`restore_translations.rb`、target 設定、`strip_translations.rb`，再做 static build。
tracked ledger 是 [`../translations/m2-ui-batch-1.jsonl`](../translations/m2-ui-batch-1.jsonl)，
只含 source hash／target metadata／term key，不含 source object；完整本機 working、
patched ROM、BPS、render 與 report 都在 ignored `work/`。

### batch-1 static gate

| 項目 | 結果 |
| --- | --- |
| target | `526432`／`0x08080860`；source raw SHA `b5635bbc…`；ledger SHA `538fa597…`；target `存在`，4-byte payload，2 units，16px width，NUL，無 controls |
| narrow allocator | slots `543/542`；code units `0xE883/0xE783`；free narrow slots before 165；protected blank referenced `[0,57,58]` preserved；wide new slots 0 |
| glyph/render | slot 543 glyph `2122a153…`／4bpp `99d93d74…`；slot 542 glyph `9134e073…`／4bpp `d13bd68f…`；target 1bpp `e8e40439…`／4bpp `7423be02…` |
| adjacent | `526424` base／patched payload SHA `d00ed112…` identical；base／patched 1bpp `20b2c971…` identical；base／patched 4bpp `c0ef81f3…` identical |
| ROM/BPS | patched ROM `e6ed5116…`；BPS 66 bytes／`1fe27b27…`；apply byte-identical |
| runtime | `pending; static render gate only`；不把 PGM／hash 當成 mGBA 畫面證據 |

同一 slice 也刻意嘗試 glossary 的精神指令 `string_id=509548`；source raw SHA
`185566ea…`、觀察 line width 24，但兩個 glyph 都分類為 `wide`。因 M1.8 寬字新槽
容量是 0，allocator 以 `wide_glyph` fail-closed 拒絕，沒有建立 translation 或修改
ROM。這是有效的負向 gate，不是把 wide term 偷換成窄字 POC。

因此 batch-1 證明的是一筆 source-safe、同長、窄字 static `ai_draft` 與一個 wide
candidate 的拒絕路徑；它沒有證明 generic 「有／無」語境、完整 UI partition、
newline／speaker semantics、patched runtime screen 或批量 translation readiness。

## 2026-08-16：M3 bounded multi-record static reinsertor

為避免把單筆 M1.8 builder 誤當成完整回插器，本輪新增
[`tools/m3_reinsert.py`](../tools/m3_reinsert.py)。它只接受一組或多組成對的 source-safe
ledger 與本機 restore working record，先逐筆驗證 source record／ROM bytes／ledger
UTF-8 hash／Shift-JIS payload／NUL／glyph-only narrow shape／同長 target，再以同一份
occupancy 建立 global Unicode codepoint → narrow slot → two-byte code unit map。不同
record 重複使用同一 codepoint 時共用配置，不會因逐筆 patch 把同一個 glyph slot 覆寫成
不同字；report 只寫 hash、offset、slot、count、control metadata，不寫 source text。

### 可重現的兩筆合併 POC

使用 M1.8 `526424` ledger 與 M2 batch-1 `526432` ledger，兩筆均為兩窄字／16px／
NUL／無 control token。global allocator 從 165 個安全空槽配置 4 個 unique glyph，
slots `[543,542,541,540]`，保護 `[0,57,58]`；同一 target codepoint 跨 record 只配置
一次。source-safe report 在 [`m3-reinsert-contract.json`](m3-reinsert-contract.json)：

| 項目 | 結果 |
| --- | --- |
| records | 2；source／ledger hash matches 2/2；same-length 2/2；control tokens 0 |
| font／allocator | Unifont／OFL hashes match；narrow-only；4 allocations；wide new slots 0 |
| patched ROM | base `12b706b6…` → `e275e9a7…`；只報 metadata，ROM 留 ignored `work/` |
| BPS | 97 bytes／`b85317d2…`；apply byte-identical |
| runtime | `pending; static reinsert only` |

這個 bounded contract 將「可逆回插」收斂到兩筆窄字 static slice，但仍不代表完整
codepage、wide resource 擴容、opaque／控制碼、newline／speaker／branch layout、
自然 mGBA 畫面或全語料翻譯已完成；本輪另以 re-extraction comparator 驗證這兩筆及
其餘 untouched records，不能把結果外推成完整 engine coverage。

## 2026-08-16：M3 bounded re-extraction／diff-range audit

新增 [`tools/m3_roundtrip_audit.py`](../tools/m3_roundtrip_audit.py)，以 clean ROM、
ignored M3 patched ROM、ignored restored working records 與 reinsert report 做唯讀重抽取。
它對整個 `0x076000..0x082490` source pool 逐筆驗證 base bytes 與本機 strict Shift-JIS
source equality，對 ledger target 以 report 的 codepoint→code-unit metadata 重建預期
payload，再檢查 target／NUL／length；其餘 records 必須與 clean ROM byte-identical。
最後把所有 ROM diff 限制在兩個 target record ranges 與已配置 glyph slot ranges，
report 不含 source text。

### M3 POC comparator result

| 項目 | 結果 |
| --- | --- |
| base source re-extraction | 2325/2325 strict source bytes 相符 |
| target exact | 2/2；target payload hash 由 report 重建並核對 |
| untouched exact | 2323/2323；NUL terminator／record boundary 未移動 |
| diff safety | actual ROM changes 僅落在 target／glyph allowed ranges；outside equal |
| source safety | `source_text_emitted=false`；只輸出 IDs／hash／count／range |
| scope | static two-record POC；完整 rebuilt corpus、wide／opaque／control／runtime 仍 pending |

這使 M3 的「重抽取／round-trip」由單純 `cmp` 擴展成 record-level comparator，摘要在
[`m3-roundtrip-audit.json`](m3-roundtrip-audit.json)；但它仍不是完整文本 extractor
或 runtime QA。下一步必須在不誤命名 opaque token 的前提下，決定 full-corpus
translation coverage 與 wide resource／codepage 擴容策略。

## 2026-08-16：M4 前置全語料 structural inventory

新增 [`tools/m4_corpus_inventory.py`](../tools/m4_corpus_inventory.py)，只讀 clean A6SJ
與 ignored `*-decoded.jsonl` source table，重新驗證每筆 Shift-JIS payload、NUL 邊界與
M1.7 token encode no-op，然後只依 glyph class／opaque shape 分類。工具不輸出 source
text，也不把 offset page 當成話數、UI 或劇情語意；完整 local output 留在 ignored
`work/m4-corpus-inventory.json`，tracked hash／count 摘要在
[`m4-corpus-inventory.json`](m4-corpus-inventory.json)。

### 可重現結果

| structural partition | records | offset index SHA-256 |
| --- | ---: | --- |
| glyph-only narrow | 939 | `d428a46d…` |
| glyph-only mixed narrow/wide | 833 | `b8a263b5…` |
| glyph-only wide | 417 | `94543c7a…` |
| opaque／unaligned | 136 | `e46ce63b…` |

全語料 strict source／NUL／token encode no-op 是 `2325/2325`；glyph token 是
`15885`（narrow `11902`、wide `3983`），opaque token 是 ASCII／format-like `1032`
與 unaligned tail `88`。目前窄字 static reinsert 的結構入口只能是全窄 939 筆，
其餘 `1386` 筆拒絕；寬字新槽 capacity 仍固定為 `0`。這個 inventory 收斂的是
可審核的格式覆蓋邊界，不是語意翻譯、newline／speaker 解碼或 runtime 覆蓋。

本輪完成 M4 的前置資料盤點，但沒有因此擴大 ledger 或宣稱完整翻譯；下一步仍須
以 caller／自然畫面完成語意分區，證明 wide resource 策略，再逐批建立可回插的
zh-TW ledger。

## 2026-08-16：M4 bounded wide existing-slot reuse audit

新增 [`tools/m4_wide_reuse_audit.py`](../tools/m4_wide_reuse_audit.py)，只讀 clean ROM
與 ignored strict source table，對每個 source Unicode character 的標準 Shift-JIS
雙位元組建立 source-context identity，再以已證明的 `0x080085FC` code-unit formula
解析到既有 wide resource slot。它不從 bitmap 位置猜 Unicode、不配置新 wide slot、
不改 ROM；tracked 摘要在 [`m4-wide-reuse-audit.json`](m4-wide-reuse-audit.json)，
完整 identity rows 只留 ignored `work/m4-wide-reuse-audit.json`。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| source records | 2325；wide occurrences 3983 |
| source-context identities | 743 個 Unicode／code-unit／slot 一對一 mapping |
| resource | `0x08120DBC..0x0814F664`；stride 26；payload 24 bytes；physical slots 7332 |
| existing payload | 743/743 對應 slot 的 payload initialized；slot index hash 與 M1.7 resource audit 相符 |
| runtime boundary | `U+79FB`／`0xDA88`／slot 905 有 M1.6 runtime positive；其餘 742 個 static-only |
| allocation policy | 新 wide slot 0；未在 source-context map 的 target reject；font expansion 未實作 |

這個 slice 只提供「可重用既有 wide glyph」的 source-safe static boundary，不能把
743 個 identity 當成 743 個 runtime renderer proof，也不能解除 mixed／opaque record
的其他 layout gate。下一步仍須完成控制碼／newline／speaker 語意與完整 encoder，並以
自然或 controlled runtime 覆蓋翻譯後的 wide consumer。

`tools/m4_wide_reuse_contract.py` 再把這個 boundary 變成可測的 policy：它只接受
existing identity map 中的 Unicode，對 unknown target codepoint、new wide slot 與
font expansion 都回傳 reject；它不寫 ROM。摘要在
[`m4-wide-reuse-contract.json`](m4-wide-reuse-contract.json)，因此仍不能替代完整
wide resource expansion 或 runtime proof。

## 2026-08-16：M4 bounded source provenance join

本輪不重新做 pointer scan；`tools/m4_source_provenance.py` 只讀先前 M1.5 已建立的
ignored `pointer-caller-report.json`，再與 2325 筆 strict source table、12 筆已提交
static ledger 與 M1.6 glyph provenance 做 source-safe join。輸出只含 structural
partition、caller／literal confidence count、ID／caller index hash 與 coverage count，
不含 source text，也不替 pointer target 命名語意。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| pointer evidence | 4,947 aligned refs；915 literal candidates；195 pointer runs |
| exact source join | 609 exact source candidates；370 distinct source records；confidence high 321／medium 221／low 67 |
| literal provenance | literal pool 393；pointer-table member 216；caller／call-target 只保存 index hash |
| structural join | narrow 939（exact records 83）；mixed 833（126）；wide 417（101）；opaque／unaligned 136（60） |
| translation/runtime coverage | 11 static translation IDs 全在 narrow partition；M1.6 runtime identity IDs 2（narrow 1／wide 1） |
| semantic boundary | `semantic_partition_status=unclassified`；natural runtime screen `pending`；pool 外與未知 pointer `unconfirmed` |

這個 milestone 只證明既有 caller evidence 能被分區統計，沒有完成話數、分支、UI、
機體／駕駛員／武器／精神或戰鬥／話間語意分類；下一步仍須自然／controlled caller
context 才能解除該邊界。

## 2026-08-16：M4 full-corpus fail-closed encoder boundary

為避免把 12 筆 static POC 誤稱為 full encoder，本輪新增
[`tools/m4_full_corpus_gate.py`](../tools/m4_full_corpus_gate.py)。它重讀 clean ROM 與
ignored strict source table 的全部 2325 筆，逐筆核對 Shift-JIS、NUL 與 token encode
no-op，再以 source-safe ledger ID 與 M4 reinsert／round-trip report 核對實際可回插集合。
工具不生成未證明的 target，也不替 mixed／wide／opaque record 猜控制碼或語意。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| source gate | strict Shift-JIS 2325/2325；NUL 2325/2325；token encode no-op 2325/2325 |
| accepted static subset | ledger 12 筆，全數為 glyph-only narrow；reinsert 12/12；same-length true；wide new slots 0 |
| not-yet-translated | 927 筆 glyph-only narrow |
| fail-closed partitions | mixed 833；wide 417；opaque／unaligned 136 |
| round-trip | base source 2325/2325；target 12/12；untouched 2313/2313；outside allowed ranges equal |
| status | `full_encoder_status=fail_closed_subset_only`；semantic translation complete `false` |

這個 gate 完成的是「全語料可重讀、已批准 subset 可回插、其餘明確拒絕」的安全邊界，
不是完整語意 encoder、完整 ledger 或發行版翻譯。

## 2026-08-16：M4 bounded UI batch-2 duplicate-codepoint POC

在 M1.11 的 NUL／two-byte／width gate 已明確適用的前提下，選取另一筆 source
`string_id=512228`：它是全窄 glyph-only、2 units、16px、NUL 終止且沒有 control token。
流程依序使用 `m18_narrow_allocator.py seed-ledger`、`restore_translations.rb`、target
設定、`strip_translations.rb`，tracked ledger 只保留 source hash 與 target metadata，
source object 仍只在 ignored working。target 是同長 zh-TW `沒有`，沒有新增專有名詞。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| target | `512228`；raw SHA `d00ed112…`；ledger SHA `868310e1…`；4-byte payload；2 units；16px；NUL；control 0 |
| combined static reinsert | 3 records；4 unique narrow allocations；batch-2 相對 M3 batch 新增 unique glyph `0`；`U+6C92`／`U+6709` reused |
| BPS | 105 bytes／`3781a7e2…`；apply byte-identical；patched ROM `1c4940bd…` |
| re-extraction | source 2325/2325；target 3/3；untouched 2322/2322；changed bytes 60；outside allowed ranges equal |
| runtime | `pending; static re-extraction only`；不把 static hash 當成畫面證據 |

這是 duplicate-codepoint／第二筆同長 UI 的 bounded POC，不是批量翻譯批准。mixed／
wide／opaque、控制碼／newline／speaker、完整語意分區與 mGBA patched screen 仍未完成。

## 2026-08-16：M4 bounded UI batch-3 24px source-shape POC

為驗證不只 16px 短字，選取 5 筆已確認全窄 glyph-only、3 units、24px、NUL 終止、
control token 0 的一般 UI label。target 為 source-safe ledger 中的「類型：」「尺寸：」
「資料：」「技能：」「完成：」，沒有專有名詞。此前 `m18_narrow_allocator.py`
`seed-ledger` 對所有 record 寫死 16px；本輪修正為 strict source tokenization 的
實際 line width，並以 escaped synthetic test 固定 3 narrow units → 24px。source object
仍只在 ignored working，tracked ledger 只保留 hash／target metadata。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| selection | 5 records；每筆 6-byte payload／3 units／24px／NUL；control 0；narrow-only |
| combined static reinsert | 8 records；15 unique allocations；slots `529..543`；`U+FF1A` 跨 record reuse；protected `[0,57,58]` preserved |
| BPS | 283 bytes／`25546b61…`；apply byte-identical；patched ROM `4c840fec…` |
| re-extraction | source 2325/2325；target 8/8；untouched 2317/2317；changed bytes 199；outside allowed ranges equal |
| runtime | `pending; static re-extraction only`；不把 static hash 當成畫面證據 |

這個 slice 擴大的是已證明窄字／單行／無控制碼的 static label 覆蓋，不是完整翻譯。
變長、wide、mixed、opaque、newline／speaker／branch semantics 與 natural mGBA screen
仍維持 fail-closed／pending。

## 2026-08-16：M4 bounded UI batch-4 48／56px status slice

在 batch-3 已驗證 source-shape 寬度可由 tokenizer 計算後，本輪再選三筆不含控制碼、
全窄 glyph-only、NUL 結尾且可保持原長度的 UI／status record：`513060`、`513076`、
`517848`。tracked [`../translations/m4-ui-batch-4.jsonl`](../translations/m4-ui-batch-4.jsonl)
只保存 source hash、target metadata 與 `ai_draft` 狀態；本機 source／working、patched
ROM、BPS 與 raw render 仍在 ignored `work/`／`roms/`。本輪沒有把預檢到的 wide record
`516460` 加入翻譯，維持 wide-new-slot `0` 的 fail-closed 邊界。

`tools/m4_ui_batch4.py` 會重新讀取 ignored strict source table，逐筆核對 ROM bytes、
Shift-JIS、NUL、narrow-only token shape、ledger UTF-8 hash 與 target unit count，並把
static reinsert／round-trip／BPS 套用結果收斂成不含 source text 的 tracked metadata。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| selection | 3 records；6／6／7 narrow units；48／48／56px；NUL；control 0；narrow-only |
| targets | `513060`、`513076`、`517848`；target codepoint 與 payload 只以 metadata／hash 保存 |
| combined static reinsert | 11 records；26 unique narrow allocations；protected `[0,57,58]` preserved；wide new slots 0 |
| BPS | 472 bytes／`5c64fc7d…`；apply byte-identical；patched ROM `d6c89f55…` |
| re-extraction | source 2325/2325；target 11/11；untouched 2314/2314；changed bytes 355；outside allowed ranges equal |
| runtime | `pending; static re-extraction only`；仍不把 static hash 當成 mGBA 畫面證據 |

這個 slice 只擴大已證明的窄字／單行／無控制碼／固定長度 static coverage；它沒有解除
wide、mixed、opaque、newline／speaker／branch semantics，也沒有宣稱完整 encoder、
自然畫面或完整翻譯完成。

## 2026-08-16：M4 bounded UI batch-5 64px prompt slice

本輪選取 `string_id=516324` 的單行窄字 prompt，source shape 為 8 units／64px、NUL、
control token 0；target 以同長 `ai_draft` ledger 保存。`tools/m4_ui_batch5.py` 重用
batch-4 的 source-safe validator，並以 restore／working／strip、global reinsert、BPS
與全池 round-trip 產生本輪摘要 [`m4-ui-batch5.json`](m4-ui-batch5.json)。

### 可重現結果

| 項目 | 結果 |
| --- | --- |
| selection | `516324`；16-byte payload／8 units／64px／NUL；control 0；narrow-only |
| combined static reinsert | 12 records；28 unique allocations；protected `[0,57,58]` preserved；wide new slots 0 |
| BPS | 518 bytes／`f853f78d…`；apply byte-identical；patched ROM `6723931d…` |
| re-extraction | source 2325/2325；target 12/12；untouched 2313/2313；changed bytes 393；outside allowed ranges equal |
| runtime | `pending; static re-extraction only`；不把 static hash 當成畫面證據 |

這個 slice 仍只擴大窄字／單行／無控制碼／固定長度 static coverage；完整 semantic
partition、wide／mixed／opaque、newline／speaker／branch 與自然 mGBA screen 仍 pending。

### 第一輪結論（M0／M1 初輪快照；M1.8 更新見上）

| 問題 | 狀態 |
| --- | --- |
| ROM 身分／CRC | 已確認（A6SJ／`efb45117`） |
| 有界靜態文字池／分區線索 | 已確認 `0x076000..0x082490` 的 NUL 結尾 Shift-JIS 候選池；完整文本仍未確認 |
| 字型／glyph addressing | M1.8 已確認窄字 8×12／12-byte packing、544-slot formula 與 allocator；寬字新槽仍為 0 |
| glyph identity | M1.6 已確認 `ラ`／`移` 兩個 strict source-context sample；字符表候選仍不能直接擴張成完整 codepage |
| codepage | 已確認有界靜態池為嚴格標準 Shift-JIS，並以兩個 runtime code unit 走通 lookup；池外文本未確認 |
| 指標表 | 有界池已有 4-byte 絕對 pointer 命中與群組；語意／caller／runtime 未確認 |
| runtime 邊界 | ROM entry／VRAM transfer、font slot writer 與兩個 bounded glyph consumer 均有陽性；自然 boot／menu 覆蓋仍有限 |
| 壓縮 | 只有 BIOS／簽章候選，未確認與文本相關 |
| 控制碼／終止碼／行寬 | NUL／窄字 bounded width 已確認；newline／完整控制語意仍未確認 |
| 可逆回插 | 十二筆同長 static POC＋BPS round-trip 已確認；完整 encoder／場景 QA 未確認 |
| 翻譯 | 十二筆 source-safe `ai_draft` static POC；尚未開始全語料批量翻譯 |

## 下一輪入口

1. 以獨立 mGBA／controlled consumer 驗證 patched target 與相鄰 untouched record；
   raw output 留 ignored，不把 static render 擴張成自然畫面 QA。
2. 定義 newline／opaque token、完整行數／說話者／分支 layout，並以更多不含專名
   的短 UI record 擴大 allocator QA；wide 新槽仍不可用。
3. 以 target／font／ROM hash、ledger restore／strip 與 BPS gate 維持可重現；
   只有 full-game encoder、容量與場景 QA 完成後才擴大翻譯批次。M4 inventory
   只把 939 筆全窄 record 標成結構入口，沒有替其他 1386 筆解除 opaque／wide gate。

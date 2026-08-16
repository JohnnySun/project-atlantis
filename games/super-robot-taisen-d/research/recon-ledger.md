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

### 第一輪結論（M0／M1 初輪快照；M1.6 更新見上）

| 問題 | 狀態 |
| --- | --- |
| ROM 身分／CRC | 已確認（A6SJ／`efb45117`） |
| 有界靜態文字池／分區線索 | 已確認 `0x076000..0x082490` 的 NUL 結尾 Shift-JIS 候選池；完整文本仍未確認 |
| 字型／glyph addressing | M1.6 已在兩個 initialized ROM base 上完成 bounded glyph bytes／tile output hash；完整字型格式仍未確認 |
| glyph identity | M1.6 已確認 `ラ`／`移` 兩個 strict source-context sample；字符表候選仍不能直接擴張成完整 codepage |
| codepage | 已確認有界靜態池為嚴格標準 Shift-JIS，並以兩個 runtime code unit 走通 lookup；池外文本未確認 |
| 指標表 | 有界池已有 4-byte 絕對 pointer 命中與群組；語意／caller／runtime 未確認 |
| runtime 邊界 | ROM entry／VRAM transfer、font slot writer 與兩個 bounded glyph consumer 均有陽性；自然 boot／menu 覆蓋仍有限 |
| 壓縮 | 只有 BIOS／簽章候選，未確認與文本相關 |
| 控制碼／終止碼／行寬 | 未確認 |
| 可逆回插 | 未確認，尚未建立 encoder／builder |
| 翻譯 | 未開始 |

## 下一輪入口

1. 以已知 queue／UI caller 為邊界，擴大自然畫面與分支／話數資料的 renderer
   覆蓋；不把兩個 controlled sample 當作完整劇情 coverage。
2. 定義 control token、換行／行寬、說話者與字串容量，並確認窄／寬字 codepage
   的完整 glyph table 與缺字策略。
3. 以現有共用 core GDB／renderer 工具做少量可重現場景驗證；每次 GDB 斷線都
   重啟本 session 自己的 mGBA，raw output 留 ignored。
4. 只有在上述邊界、encoder、回插與 round-trip 條件都可審核後，才建立第一批
   zh-TW 翻譯與回插實驗；目前 translation 仍未開始。

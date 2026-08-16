# 《真・女神轉生 II》漢化工作區

本目錄只處理日版 GBA《真・女神転生II》（A5TJ），目標為臺灣繁體 `zh-TW`。ROM、sav、完整解出的原文、VRAM／OAM dump、渲染圖片與暫存構建只保存在本機，不進 Git。

## M0/M1/M1.5/M1.6/M1.7/M1.8/M1.9/M1.10/M1.11/M1.12/M1.13/M1.14/M1.15/M1.16/M1.17 基準狀態（2026-08-16）

- ROM header 身分已確認：`DDS_2`、`A5TJ`、maker `EB`、revision `0`、8 MiB。
- 本機候選的 ROM CRC32 為 `af40cc99`，SHA-256 為 `819a6a19a40bfbe7608f4b813dc18285c827f64e1523561ffe8e10ce8ab5991e`；完整指紋和 header complement 異常見 `research/recon-20260816.md`。
- header complement 儲存值 `0x4a`、依標準公式計算值 `0x7c` 不一致；mGBA 仍能執行並顯示畫面，因此本階段不修改 ROM，也不把「可執行」誤當成 dump 來源乾淨的證明。
- `tools/recon_static.py` 是本作自有的唯讀第一輪掃描器：接受 raw GBA 或只有一個 GBA 成員的 ZIP，只輸出 header、雜湊、尾端、候選計數與偏移，不輸出完整原文。
- 2367 headless GDB 回合已完成：讀取 watchpoint 確認 KEYINPUT 消費點；Start 輸入後讀取 VRAM、palette、OAM，並依 OAM 實際排列渲染出遊戲內日文免責文字。
- M1.5 已完成一個有界來源分析回合：Start 後有 46 個 active sprite、84 個 unique OBJ tile；完整 sprite glyph 在 ROM、IWRAM、EWRAM 與 bounded LZ77/RL stream 均無 byte-identical match，也沒有因此推導出 font stride。
- 已確認 OAM buffer 的 IWRAM source 與 DMA3→OAM consumer；OBJ tile 的固定 DMA candidate 已記為 provisional，尚未宣稱是免責畫面的實際 source。
- 目前只確認「文字確實在 OBJ sprite 路徑上被消費並顯示」；尚未確認文字儲存表、codepage、指標／bank、壓縮、控制碼、惡魔／技能／道具／劇情資料邊界或可逆回插路徑。
- M1.6 已把 provisional `0x080baecc` 完整驗證為固定 9-instruction Thumb DMA3 setup：literal pool 在 `0x080baee0`–`0x080baef0`，固定 `0x02001000` → `0x06013000`、control `0x84000700`；它不是 queue parameter。其餘七個 `0x06013000` copy 也是同一個 byte pattern 的固定副本；先前記為 `0x080bbcdc` 等五個位址的是 routine 的第一條 source `STR`，真正 entry 已在研究紀錄中回退 4 bytes。
- M1.6 已確認一個獨立的通用 resource/event queue：drain `0x080ad01c`、producer `0x080ad0fc`、base `0x02009004`、64 個 stride `0x64` entry、callback table `0x0815eeec`。reset→Start live entry `0x02009068`／`0x020090cc` 只攜帶 ROM resource pointers `0x08509cf8`／`0x08509cd0`；這不是已證明的 glyph transfer queue。
- M1.6 的 formal bounded probe 在 35 秒 reset→Start window 讀到 KEYINPUT 6 次、送出 Start；八個固定 OBJ-DMA site、`0x080baef0` staging candidate 與 `0x02001000` write watch 都是 0 hit。DMA3 register、queue entry、queue callback 與 BIOS LZ77 consumer 的 metadata 有捕捉，但唯一 LZ77 目的地為 `0x0200f874`，不是 staging buffer。這是可重現的陰性窗口，不是「全遊戲沒有」的證明。
- `0x080baef0` 仍是最精確的 glyph-staging candidate：兩次 `LZ77UnCompWram` wrapper call 目標分別為 `0x02001000` 與 `0x02002000`；它在本次畫面窗口未命中。附近 `0x081869c8` descriptor 的自然 command drain 仍待以 live indirect dispatch 追蹤，不能把 table pointer 當成 source table。
- M1.7 已完成 descriptor／selector 有界切片：`0x08182b70` 是
  `0x08182b54 + 7*4`，選出的 descriptor 為 `0x081869c8`；selector
  `0x080ba8d8` 的三個 direct BL caller、ARM7TDMI boundary、literal pool、
  callback table `0x0815eeec`（25×8）與 descriptor sentinel stream 均已記錄於
  `research/m1.7-descriptor-20260816.md`。descriptor window 是 variable-length，
  不是固定 stride，也沒有因此建立 source table。
- M1.7 natural A/Start/方向鍵 transition 未命中三個 selector caller、
  `0x080baef0` 或 `0x080bafb8`；generic queue 的 source/LZ77 activity 仍是
  `0x08509cf8`／`0x08509cd0` 與 `0x084f9cd0 → 0x0200f874`。一個明確標記的
  synthetic `group=1,index=7` fallback 只確認
  `0x081869c8 → 0x080ad0fc(pointer,0xffff)` producer link，並在 return guard
  fail-closed；不能冒充自然 resource selection，也沒有取得 glyph writer。
- 尚未開始翻譯，也沒有可提交的翻譯記錄；專有名詞會在真正建立批次前依 `AGENTS.md` 查 Wikipedia zh-tw、巴哈姆特及其他獨立來源。
- M1.8 已從 fresh process 起點先 arm `0x03006950` pointer、相鄰 halfword 與 `0x0203db40` counter watches；三條明確 natural transition cohort 與同一路徑的窄 initializer-only follow-up 都沒有 pointer/counter write、selector caller 或 descriptor hit。完整證據與 22 個 provisional static candidates 見 `research/m1.8-selector-initializer-20260816.md`。
- M1.9 已完成四個 priority writer 的 bounded Thumb static mapping 與 caller 1–3 層：`0x0813e428` 以 incoming `r0` 替換 selector pointer、`0x0813e574` 從 RAM `0x030068c0` 還原，`0x0812f2b4` 的明確分支則寫入 ROM `0x08036666`；`0x080bee40`／`0x081534ae` 的 caller argument 只得到 provisional ROM-table provenance，尚未連到 glyph source。證據見 `research/m1.9-selector-state-mapping-20260816.md`。
- M1.10 已將兩個 ROM provenance 分開：`0x08198a98` 是含 sentinel 的 variable word stream；`0x087df54c` 是 125 筆、stride `0x8` 的 key＋ROM pointer 區段。reader 只在 `0x080bee40`／`0x081534ae` 將它們送入 selector swap，前八個有限 target window 沒有 LZ77 header 命中；仍未得到 glyph/source table。證據見 `research/m1.10-rom-table-shape-20260816.md`。
- M1.11 已把 OAM metadata consumer 與 OBJ VRAM destination family 分開：`0x030033f0 → DMA3 → 0x07000000` 的參數與 caller chain 已驗證；`0x06010000` 有 12 個 bounded literal consumers，8 個 `0x06013000` fixed-DMA pattern 仍有效。這些是 OAM／destination 證據，不是文字 source；證據見 `research/m1.11-obj-consumer-20260816.md`。
- M1.12 static fallback 已在 12 個 OBJ-VRAM reference 中辨識 7 個 DMA3 source edges，其中 `0x02001000 → 0x06010000` 出現兩次；另 5 個因 arithmetic/shared control 保持 unresolved。自然 runtime probe 已建立，但本回合 GDB listener 在 attach 前受本機 socket／port 環境阻擋，沒有把它記成 runtime negative；證據見 `research/m1.12-obj-source-map-20260816.md`。
- M1.13 已沿 `0x02001000` staging edge 完成 bounded static resource map：`0x0813ef64` 是 Huff→LZ77-WRAM transform，`0x0813ef65` callback pointer 形成 16×8、stride `0x18` 的 record candidates；每筆 `+4` 欄位是 ROM-pointer-shaped source。這仍不是文字表，尚未取得自然 source/index/code-unit argument；證據見 `research/m1.13-staging-resource-map-20260816.md`。
- M1.14 已把 `0x0879243c[5] → 0x0813f22c → 0x08794e24 → opcode 0x0c → callback-table[12] → 0x0813ef65` 靜態接通：128 次 callback 前均有 `0x0c`，source `+0x04` 全為 ROM pointer，`r2=0..7` 各 16 次，並接到 Huff→LZ77 staging expression。這是 source/staging provenance，不是自然 runtime hit、文字表或 glyph identity；證據見 `research/m1.14-resource-reader-20260816.md`。
- M1.15 對同一批、且只對這批 16×8 source candidates 做本作自有的 GBA Huff→LZ77 bounded decoder：128/128 是 `0x24`、4-bit Huffman，128/128 解出 `0x10` LZ77，最後 payload 皆為 4096 bytes（128 個完整 4bpp tile block），唯一輸出 hash 仍有 122 組。這確認它們是可重抽取的 resource payload class／staging bank input，不是文字 source table；沒有取得 code-unit、Unicode 或 glyph identity，證據見 `research/m1.15-source-class-20260816.md`。
- M1.16 將同一批 128 筆 nested resource 與固定 hash 的 Start-screen capture 交叉：46 個 active sprite、84 個 unique tile、184 個 tile occurrences；32-byte aligned exact、hflip、vflip、rotate180、nibble-swap 的完整 sprite 都是 0 hit，非零 tile 也是 0/173 hit（另有 11 個空白 occurrence）。這是「本 capture 中不是該命名 resource set 的直接 OBJ source」的有界 negative，不把資源全域命名成非文字；證據見 `research/m1.16-resource-obj-cross-20260816.md`。
- M1.17 已找到第一條命名的文字／code-unit consumer edge：ROM `0x08163444 + index*0x0a` → Thumb reader `0x080b6460`，以 `ldrb` 消費 byte unit 並以 `0x20` 停止，再由 `0x080b64e4` 將 descriptor `0x08163638` 送入 `0x080aa1f4`。只驗證前 37 筆 ASCII/padding-class record 的 address/hash/length/count metadata；`0x080aa1f4` 仍是 OAM record writer candidate，尚未證明日文主劇情、codepage、glyph identity 或 staging→OBJ 因果鏈。證據見 `research/m1.17-text-consumer-20260816.md`。

## 可重現入口

在本機合法持有的日版候選檔案上執行：

```sh
python3 games/shin-megami-tensei-2/tools/recon_static.py /path/to/A5TJ.zip --pretty
```

M1.6 的固定 DMA／queue 靜態驗證不會做 glyph pattern scan：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m16_queue_probe.py \
  --rom /path/to/A5TJ.gba --static-only \
  --output /private/tmp/smt2-m16-static.json
```

若要重跑已啟動、且只屬於本作的 mGBA GDB port `2367`，runtime report 只保留
address、PC/LR、selected registers、length、hash 與 count；不要把 output 放進 Git：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m16_queue_probe.py \
  --rom /path/to/A5TJ.gba --port 2367 --press-start \
  --output /private/tmp/smt2-m16-runtime.json
```

可以再以 `--summary --input-report` 產生可放入研究筆記的 metadata 摘要。

M1.7 selector／descriptor 靜態與 bounded runtime 入口：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m17_descriptor_probe.py \
  --rom /path/to/A5TJ.gba --static-only \
  --output /private/tmp/smt2-m17-static.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m17_descriptor_probe.py \
  --rom /path/to/A5TJ.gba --port 2367 --lean-transition \
  --key-sequence a,start,a,b,down,a \
  --output /private/tmp/smt2-m17-runtime.json
```

`--force-selector-index 7` 是只供工程驗證的 synthetic、fail-closed fallback；
它會明確標示 PC/register override，不得當成自然場景證據，也不應在未審核的
遊戲狀態上繼續 emulator 執行。

M1.8 initializer／natural transition probe：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m18_initializer_probe.py \
  --rom /path/to/A5TJ.gba --port 2345 --path-id boot-start \
  --key-sequence a,start,a,b,down,a --output /private/tmp/smt2-m18.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m18_initializer_probe.py \
  --rom /path/to/A5TJ.gba --port 2345 --initializer-only \
  --key-sequence a,start,a,b,right,left,down --output /private/tmp/smt2-m18-init.json
```

`--initializer-only` 只保留 initializer candidates 與窄 selector-table watches；
它沒有任何 selector/state 寫入選項。`--summary --input-report` 可產生不含事件
payload 的 metadata 摘要。

M1.9 selector state mapping（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m19_state_mapping.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m19-static.json
```

工具只追 M1.8 已列出的四個 writer、tracked global literal/store 與最多三層
Thumb BL caller；它不做 glyph scan、不輸出 instruction/raw source，也不建立
source table。

M1.10 ROM table shape（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m110_rom_table_shape.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m110-static.json
```

工具只檢查 `0x08198a98`／`0x087df54c` 的 bounded word/pair shape、literal
reader 與少量 target-window hash；不輸出 table key、raw bytes 或完整原文。

M1.11 OAM／OBJ consumer mapping（只做已知 consumer 與 destination literal，
不做 glyph scan）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m111_obj_consumer.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m111-static.json
```

工具輸出 `0x030033f0 → 0x07000000` OAM DMA、四個 bounded OAM node、
`0x06010000` 的 12 個 literal consumers 與八個已知 `0x06013000` fixed-DMA
site 的 address／boundary／hash／count metadata；不輸出 raw tile、instruction
bytes、完整原文或 source table。

M1.12 source-class static mapping 與 runtime probe：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m112_obj_source_map.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m112-static-source.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m112_obj_runtime.py \
  --port 2367 --rom /path/to/A5TJ.gba \
  --key-sequence a,start,a,b,down,a,right,a \
  --output /private/tmp/smt2-m112-runtime.json
```

static tool 只辨識已知 `0x06010000` reference 周圍的 DMA3 fields；runtime tool
只裝同一批 breakpoint、DMA3 SAD/DAD/CNT 與 KEYINPUT watch，輸出 metadata，
不把 attach 前的 socket failure 當成遊戲陰性。

M1.13 staging writer／resource record static map：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m113_staging_resource_map.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m113-static.json
```

工具只追 `0x0813ef64` 的 bounded Huff→LZ77 transform、`0x0813ef65` 的
16×8 callback record candidates、resource initializer 與 callback registration；
輸出 address／hash／length／count／region metadata，不輸出 raw record、解壓
payload、glyph、完整原文或 source table。

M1.14 descriptor reader／source provenance（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m114_resource_reader.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m114-static.json
```

工具只追 `0x0879243c[5]` 的 indirect state handler、`0x08794e24` descriptor、
opcode `0x0c` 的 callback-table reader、`0x0813ef65` source/argument fields 與
既知 staging transform；輸出 PC／callsite／boundary／address／hash／length／
count，不輸出 command bytes、source payload、glyph、完整原文或 source table。

M1.15 source class／nested decoder（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m115_source_class.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m115-static.json
```

工具只重放 M1.14 已確認的 `0x0813ef65` 128 筆 source pointer，不做全 ROM
glyph scan；輸出 Huff/LZ77 header、tree／stream 長度、輸入／輸出 hash、解碼
狀態、4bpp tile 對齊與 count，不輸出任何 compressed/decompressed bytes、字串、
圖片或 source table。

M1.16 resource→OBJ cross-check（只使用已命名 source set 與固定 capture）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m116_resource_obj_cross.py \
  --rom /path/to/A5TJ.gba \
  --vram /private/tmp/smt2-m15-start/vram.bin \
  --oam /private/tmp/smt2-m15-start/oam.bin \
  --output /private/tmp/smt2-m116-resource-obj.json
```

工具只重放已確認的 128 筆 resource payload，與一個有 hash 的 active OAM／OBJ
capture 做 32-byte aligned exact 與小型可逆 transform 比對；輸出 address／hash／
length／count／bounded offset metadata，不輸出 raw payload、tile、圖片、完整原文
或 source table。

M1.17 text/code-unit consumer（只驗證一條命名 reader 與有界 table prefix）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m117_text_consumer.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m117-text-consumer.json
```

工具只讀 `0x08163444` 起始的 37 筆、stride `0x0a` bounded prefix，驗證
`0x080b6460` 的 index×10 addressing、byte-unit/space terminator、
`0x080b64e4 → 0x080aa1f4` descriptor dispatch 與 `0x08163638` literal；輸出
address／function hash／record hash／length／count，不輸出 bytes、完整原文、
圖片、source table 或 translation ledger。

M1.18 16-bit code-unit／font-bank／source pointer table（唯讀 bounded）:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m118_codeunit_font.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m118-codeunit-font.json
```

工具沿 `0x080ac3ac`／`0x080ac334` 的 `ldrh` reader 驗證 16-bit code-unit、
`+2` advance、`0x0300` line break 與 `0x0301` terminator；再交叉
`0x080abf24` 的 `0x0815ed88` font-bank pointer table、兩個 EWRAM scratch、
`0x0815ee18` descriptor 與 OAM writer family。只輸出 function boundary、literal
edge、address／hash／length／unit-class/control count；不輸出 source bytes、
decoded text、raw font、圖片或 translation ledger。

同一工具只審核 `0x085861c8` 的 28 筆、stride `0x08` bounded pointer prefix：
保留 record ID、pointer、終止類別、長度、hash 與 `0x0300`／`0x0301` count，
不把它升格為完整主劇情表。可用 `--output` 產生研究用 metadata；其 JSON 應留在
`/private/tmp` 或 `work/`，不提交。

M1.19 reader family／inline source family（唯讀 bounded）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m119_source_family.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m119-source-family.json
```

工具沿兩個已命名 reader 的 direct BL callers，保留最多三層 caller boundary、
window hash 與 r0 setup 的 linear-bounded candidate；不把這些 candidate 當完整
CFG/data-flow proof。`0x080b52c4` 內另有 15 個有序 ROM pointer，從
`0x08162b0c` 到 `0x08162c26`，每筆以 `0x0000` 結束；工具只輸出 pointer、
termination、length、unit class/count 與 hash，不輸出 source bytes、decoded text、
圖片或 translation ledger。這個 family 與 M1.18 的 `0x085861c8`／`0x0301`
candidate 分開，category 語意仍是 provisional。

M1.20 inline selector／pointer route（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m120_inline_dispatch.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m120-inline-dispatch.json
```

工具只分析 `0x080b52c4`：確認 object `+0x24` primary field、primary-1 的
`+0x14` halfword、`+0x0c` subselector、`0x080b53a0` 五筆 jump table 與 15 筆
inline record ID route。輸出 field contract、jump target、address／hash／length／
termination metadata，不輸出原文、raw bytes、glyph 或 translation ledger；selector
語意與自然 scene 仍保持 provisional/unknown。

M1.21 named reader source inventory（唯讀 bounded）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m121_source_inventory.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m121-source-inventory.json
```

工具只消費兩個 named reader 的 direct callers；按 caller 分組 r0 literal、stack
buffer、runtime/table-derived class，對候選 ROM pointer 做最多 `0x100` bytes 的
terminator metadata probe。輸出 caller boundary、address／hash／length／termination／
count，不輸出 raw source、decoded text、圖片或 translation ledger。這是候選 family
inventory，不能把 `0x0815bed4` 等 pointer run 直接當成已命名的惡魔、技能、道具或劇情表。

M1.22 state-field／pointer route（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m122_state_routes.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m122-state-routes.json
```

工具只追 `0x080ce760`／`0x080cf414` 的 `+0x1e` halfword state load，驗證 4+5
條 literal route 全部進入 `0x0815bed4`–`0x0815c082` 的 15 筆 bounded family，
以及 named reader callsite。輸出 route address、boundary、hash、length、termination
與 count，不輸出原文、raw source、glyph 或 translation ledger；category 語意與
自然 scene 仍保持 provisional/unknown。

M1.23 encoded-string handler indirect dispatch（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m123_handler_dispatch.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m123-handler-dispatch.json
```

工具只追已命名的 `0x084f0ec0`／`0x084f1514` 兩個 command stream、各自的
producer literal/BL、callback table entry 10/11、`0x0815cccc` trampoline 與
`0x080ce760`／`0x080cf414` handler boundary。輸出 stream window hash、opcode／
record length／argument count、caller boundary 與 function hash metadata，不輸出
command word、argument value、raw source、decoded text、glyph 或 translation ledger。
工具另保留 queue entry `+0x14`／`+0x10` 與 handler state `+0x1e` 的 input
contract；A 的 argument 只報 small-selector domain count，不輸出每個值。兩個
handler 沒有 direct BL caller；這是 static indirect route，不是 runtime natural
scene proof。

M1.24 bounded source table／unit contract（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m124_source_table.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m124-source-table.json
```

工具只讀 M1.18 已命名的 `0x085861c8` 28 筆、stride `0x08`、pointer `+0x04`，
每筆最多 probe `0x100` bytes，輸出 stable local ID、address、hash、length、unit/
control/font-bank count 與 termination metadata；不輸出 16-bit unit、raw source、
decoded text、glyph 或 translation ledger。`0x0300`／`0x0301` 與 M1.18 font-bank
address expression 只當 addressing/control evidence，Unicode、寬度與 category 仍
保持 blocked。

M1.25 command context 到 source-table reader（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m125_command_context.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m125-context.json
```

工具只沿 `0x085819A0+0x0c → 0x085862A8` 的 named descriptor/command edge，確認
bounded stream 中唯一的 opcode `0x13`、callback table entry 19、queue entry `+0x20`
staged function、`0x080DD7CC` signed record index `+0x26`、`0x085861c8+index*8+4`
與 `0x080ac3ac` reader。輸出 address、boundary、hash、length、count 與 field
contract；不輸出 raw command/source/unit/glyph、decoded text、圖片或 translation
ledger。這是 static command→source-table provenance，不是 runtime natural scene、
category、Unicode 或 glyph identity proof；詳見 `research/m1.25-command-context-20260816.md`。

M1.26 context initializer／record-index domain（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m126_context_index.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m126-context-index.json
```

工具只追同一 command stream 的 `0x080DD279` initializer、`0x080DDE2C` 27-slot
selection-array writer 與 `0x080DD30C` state machine；確認 context `entry+0x26`
default `1`、array `+0x15` 的 ordinal-plus-one domain `1..27` 與 5 個 bounded
record-index writes。輸出 address、boundary、hash、length、count 與 field/domain
contract，不輸出 array values、raw source、decoded text、glyph 或 translation
ledger；這是 stable addressing/context evidence，不是 category、Unicode 或自然
runtime proof。詳見 `research/m1.26-context-index-20260816.md`。

M1.27 named reader accessor／fixed-field provenance（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m127_name_accessor.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m127-name-accessor.json
```

工具只追 `0x080e1030` 這個已命名 16-bit reader caller 與兩個 wrapper：object
`+0x40/+0x42` selector 分流到 `0x080bf32c`、`0x080bf354`、`0x080bf418` 三個
accessor，再由 `0x08198b74`／stride `0x24`／field `+0x14` 或
`0x08198eb4`／stride `0x20`／field `+0x0c` 取得固定 8-halfword field。工具驗證
stack `sp+0x0c` copy、`0x0000` append 與 `0x080ac334/0x080ac3ac` reader BL，並
以 caller threshold 將 shared table 限定為 selector `0..0xcf` 的 208 筆；secondary
window 僅為 256 筆 metadata probe，不宣稱 table extent。輸出只有 address、boundary、
literal、stride、field offset、hash、termination count 與 contract，不輸出 raw record、
16-bit unit、decoded text、glyph 或 translation ledger。沒有 runtime capture；category、
Unicode、codepage、width 與自然 selector 仍保持 provisional/unknown。詳見
`research/m1.27-name-accessor-20260816.md`。

M1.28 item-family code-unit identity cross-map（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m128_item_crossmap.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m128-item-crossmap.json
```

工具只比較 `0x08198b74` shared table 的前 8 筆 `+0x14` fixed field，使用公開日文
item sequence 作為外部 anchor；8/8 field identity match，有限 custom unit map 只
留在工具內比對。輸出只有 record address、field hash、length/count、reference ID 與
match boolean，不輸出 anchor text、unit values、decoded text 或完整 codepage。這是
第一條 code-unit→公開日文 item category 的非 OCR edge；完整 208-record category、
subcategories、Unicode/codepage、width/control、runtime 與 translation ledger 仍
保持 provisional/blocked。外部參考與證據分層見
`research/m1.28-item-crossmap-20260816.md`。

M1.29 item equipment subcategory boundary anchors（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m129_item_boundaries.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m129-item-boundaries.json
```

工具只比較 shared table `0x08198b74` 的三個 sparse record（ordinal `0x58`、
`0x80`、`0xc0`），分別作為公開 item sequence 的槍械、頭部防具、腳部防具段落
anchor；三者均以同一 custom unit map match。輸出只有 address、field hash、length、
count、reference ID 與 match boolean，不輸出原文、unit values、decoded text 或
secondary table。subcategories 的中間跨度、完整 208 筆 category、codepage、width、
control、runtime 與 ledger 仍是 provisional/blocked。詳見
`research/m1.29-item-boundaries-20260816.md`。

M1.30 demon record prefix/code-unit cross-map（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m130_demon_crossmap.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m130-demon-crossmap.json
```

工具沿 `0x080bf648`→`0x0819cb74` accessor 與 `0x080e1644` caller，檢查
`stride 0x60`、field `+0x22` 的前 16 筆 bounded record；16/16 個連續 field
對上外部 demon sequence。它同時驗證 accessor/caller Thumb boundary、table
literal、`0x080e1746` accessor BL 與 `0x080e17a6`／`0x080e17cc` reader BL。
輸出只有 address、boundary、literal、call target、field hash、length/count、
reference ID 與 match boolean，不輸出 anchor text、unit values、decoded text、
完整 codepage、glyph 或 translation ledger。`m30-demon-record-{ordinal:04d}`
與 item namespace 分開；完整 table extent、runtime selection、Unicode、glyph、
width/control 與 ledger 仍 provisional/blocked。詳見
`research/m1.30-demon-crossmap-20260816.md`。

M1.31 skill record prefix/code-unit cross-map（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m131_skill_crossmap.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m131-skill-crossmap.json
```

工具沿 leaf accessor `0x080bf5c0`→`0x0819b9f4` 與 caller `0x080bf5d8`，檢查
`index*0x1c`、field `+0x06` 的前 32 筆 bounded record；32/32 個連續 field
對上外部 skill sequence。它同時驗證 accessor leaf boundary、`0x080bf5cc`
literal、`0x080bf606` accessor BL 與 `0x080bf620`→`0x080ac218` renderer BL。
輸出只有 address、boundary、literal/call target、field hash、length/count、
reference ID 與 match boolean，不輸出 anchor text、unit values、decoded text、
完整 codepage、glyph 或 translation ledger。`m31-skill-record-{ordinal:04d}`
與 item/demon namespace 分開；完整 table extent、runtime selection、Unicode、
glyph、width/control 與 ledger 仍 provisional/blocked。詳見
`research/m1.31-skill-crossmap-20260816.md`。

M1.32 selected code-unit→font-bank→renderer provenance（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m132_font_edge.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m132-font-edge.json
```

工具只取 M1.30/M1.31 已 identity-anchored 的五個 field positions，重抽取
`0x0815ed88` bank pointer、font source address、兩個 `0x20` source block、
`0x080abf24` 的 `0x20→0x40` byte swizzle、`0x080ac218` renderer 與
`0x080aa1f4` writer edge；五筆均通過 source/hash/inverse-transform contract。
輸出只有 address、hash、length/count、reference ID 與 status，不輸出 unit、字元、
raw font/source、圖片或 translation ledger。這是 static glyph addressing edge，
不是自然 runtime 畫面像素 proof；完整 codepage、Unicode、width/control、回插與
ledger 仍 provisional/blocked。詳見 `research/m1.32-font-edge-20260816.md`。

M1.33 named writer／控制碼／layout contract（唯讀 bounded static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m133_writer_contract.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m133-writer.json
```

工具完整驗證 `0x080aa1f4` writer、`0x080a9ea8` allocator、small／large
renderer／reader 的 boundary、literal pool、callsite 與 function hash；確認
descriptor `0x0815ee18` 三個 halfword 對 OAM `attr0/attr1/attr2` 的 bounded
modulo field mapping，並以不含 ROM bytes 的 synthetic fixture 做 inverse
round-trip。兩個 named reader 的 `0x0000`／`0x0301` termination、`0x0300` line
break、16-bit/2-byte advance 與 caller-supplied fixed cursor step 也已確認。
這是可供後續 encoder 使用的 layout/control contract，不是自然 runtime pixel
capture，也不是完整 Unicode/codepage 或所有場景的像素字寬；source table、
ledger、翻譯與 patch gate 仍 blocked。詳見
`research/m1.33-writer-layout-20260816.md`。

M1.34 bounded semantic ID／unit manifest（唯讀 metadata composition）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m134_semantic_manifest.py \
  --rom /path/to/A5TJ.gba \
  --output /private/tmp/smt2-m134-manifest.json
```

工具只組合既有 M1.28–M1.31 probes 的 59 筆 bounded anchor metadata：item 8、
item boundary 3、demon 16、skill 32。每筆保留 stable ID、record address、field
offset/hash、length/count、termination、reference ID 與 identity status；四個
namespace 的 table base/stride 與 private identity hash、combined manifest hash
均可重抽取。它不重新掃描 table、不輸出 unit value、日文、raw field、glyph 或
translation ledger，也不宣稱完整 source table/codepage。M2 ledger、翻譯與 patch
gate 仍 blocked。詳見 `research/m1.34-semantic-manifest-20260816.md`。

本回合優先使用專案共用的 `core/gba/gdbstub_client.py`、
`core/gba/capture_runtime.py`、`core/gba/render_oam.py` 與本目錄的
`tools/analyze_obj_tiles.py`、`tools/trace_swi_consumers.py`、
`tools/trace_dma_consumers.py`。共用工具只負責 GDB remote protocol 與標準 GBA
memory/tile/OAM 操作；A5TJ 的 offset、來源判定與 negative evidence 均記在本目錄，
沒有套用其他遊戲的 ROM 格式假設。

## 下一個安全切片

沿 M1.29 固定的 item selector→`0x08198b74` record→fixed field→stack staging→
16-bit reader path，補完剩餘 bounded subcategory boundary；M1.30 已對
`0x0819cb74` demon accessor（stride `0x60`、field `+0x22`）建立獨立 anchor family，
M1.31 再確認 `0x0819b9f4` skill prefix，M1.32 已接通五筆
code-unit→font-bank→renderer static edge，M1.33 已固定 reader control／cursor
step 與 OAM layout contract，M1.34 已建立 59 筆 bounded semantic manifest。下一步
各 family 只選一個相鄰未 anchor record，確認 termination／field shape／stable ID
連續性；若 runtime listener 仍 blocked，最多沿同一 named source caller 三層追 RAM
object/table initializer。不能把
command pointer、font-bank shape 或人工 OCR 當成完整文字來源；item、skill、demon、
劇情與系統 data families 必須分開記錄。

不得再擴張 M1.15 resource set、重做同一 OBJ hash 分類或全 ROM glyph scan；
`0x08163444` 的 bounded ASCII/padding prefix 與 M1.18 的 28 筆 candidate 都
不可直接當完整翻譯來源。source table、ledger、翻譯與 patch 工程仍封鎖，直到
category mapping、codepage、控制碼、寬度與可逆抽取契約被確認。

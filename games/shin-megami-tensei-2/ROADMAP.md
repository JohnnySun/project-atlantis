# 《真・女神轉生 II》路線圖

## M0：身分、範圍與唯讀基準

- [x] 建立獨立 slug `games/shin-megami-tensei-2/`，不混入其他遊戲資料。
- [x] 記錄 A5TJ header、ROM size、CRC32、MD5、SHA-256 與 header complement 差異；不修補原 ROM。
- [x] 建立不輸出完整原文的 `tools/recon_static.py`。
- [x] 使用本 session 專用的 2367 headless GDB 做一次有界輸入／VRAM／OAM 回合。
- [x] 依 GBA 標準 VRAM、OBJ palette、OAM 與 4bpp/1D mapping 假設完成畫面級交叉驗證：Start 後可渲染出遊戲內日文免責文字。

## M1：文字消費者與格式偵察

- [x] 以 `Z3,04000130,2` 讀取 watchpoint 確認 KEYINPUT 的執行期消費點（PC `0x080a9a0a`），並以 active-low 值完成一次 Start 狀態轉換。
- [x] 記錄新畫面的 `DISPCNT`、BG 設定、VRAM/OAM 非零統計、OBJ tile 範圍與 46 個 active sprite 的可重現證據。
- [x] 確認至少一個實際文字消費結果：OBJ sprite 合成影像中出現三行日文免責文字。
- [~] M1.17 已確認一條 bounded ASCII/padding byte-table consumer 與 code-unit edge；這不是日文主文字表，也沒有把影像反推成原文表。
- [ ] 確認字串池／指標／bank、壓縮、換行與控制碼；不套用 SMT I、黃金太陽或其他遊戲格式。
- [ ] 分別定位惡魔、技能、道具、系統與劇情資料，並建立本作 decoder 及本機 `research/*-decoded.jsonl`。
- [ ] 以未修改資料重新抽取驗證可逆回插路徑。

## M1.5：OBJ 字型來源有界分析

- [x] 使用 `core/gba/` 工具和本作 bounded analyzer 重現 Start 後畫面，解析 46 個 active OAM sprite、84 個 unique 4bpp/1D OBJ tile，保留位置、tile index、hash 與計數，不提交 raw dump。
- [x] 對 ROM 做完整 2×2 sprite glyph exact search，以及 hflip/vflip/rotate180/nibble-swap 的有界變形 search；完整 glyph 命中為 0，沒有候選 font base/stride。
- [x] 把 IWRAM、有效分塊讀取的完整 EWRAM、固定 OAM source 與 ROM 分開比對；IWRAM/EWRAM 都沒有完整 sprite glyph 命中，零 tile match 另列為反例。
- [x] 以 4-byte 對齊、bounded output/candidate 的標準 GBA LZ77/RL scan 檢查完整 glyph；valid stream 中沒有命中，不能因此宣稱文字已壓縮格式化。
- [x] 確認一條較早的 OAM consumer：IWRAM `0x030033f0` 的 OAM buffer 由 DMA3 搬到 `0x07000000`；這是 OAM source 證據，不等於 OBJ glyph source。
- [x] 固定 OBJ-DMA routine（file `0x0baecc`，source `0x02001000`、destination `0x06013000`、control `0x84000700`）已在 M1.6 完成 entry／literal-pool／ARM7TDMI 邊界驗證；runtime 是否命中另行列在 M1.6。
- [~] M1.5 的結果是「來源範圍已縮小但尚未建立 source table」；因此 codepage、stable string ID、控制碼與翻譯仍保持封鎖。

## M1.6：固定 DMA、transfer queue 與 staging writer 有界追蹤

- [x] 完整驗證 `0x080baecc`：9 條 Thumb 指令、最後 `BX LR` 在 `0x080baedc`、alignment padding 後 literal pool `0x080baee0`–`0x080baef0`；`source=0x02001000`、`destination=0x06013000`、`CNT=0x84000700` 均由固定 literals 組裝，沒有 direct BL caller。
- [x] 驗證另外七個 `0x06013000` fixed-DMA copies。routine entry 為 `0x080bb318`、`0x080bb61c`、`0x080bbcd8`、`0x080bc584`、`0x080bc978`、`0x080d8d80`、`0x080d9448`；其中後五個 M1.5 site 名稱是第一條 source `STR`，不再混稱函式 entry。
- [x] 反組譯並記錄通用 queue drain／producer：`0x080ad01c`／`0x080ad0fc`，64 entries，base `0x02009004`、stride `0x64`，source field `+0x14`，callback table `0x0815eeec`，dynamic dispatch sites `0x080ad070`／`0x080ad0a2`／`0x080ad0be`。bounded code path 沒有獨立 head/tail slot；entry state `+0x00` 是實際 consumed state。
- [x] Formal probe 從 reset arm staging、queue entries 與 DMA3 SAD/DAD/CNT watches，並以 `core/gba/gdbstub_client.py` 重現 Start：35 秒、220 stop bound、6 次 KEYINPUT read、Start sent；queue producer 2 hits、dispatch 30 hits、LZ77 wrapper 1 hit，queue entries `0x02009068`／`0x020090cc` 各自帶有兩個已記錄 ROM source pointers。
- [x] 陰性窗口已界定：八個固定 OBJ-DMA site 0 hit、`0x080baef0` 0 hit、`0x02001000` staging write 0 hit；DMA3 metadata watch 有 hit，但 formal report 的唯一 LZ77 destination 是 `0x0200f874`，不是 `0x02001000` 或 OBJ VRAM。這不否定別的狀態／轉場，僅否定本次 reset→Start window。
- [~] 尚未建立 glyph source/staging → transform → OBJ VRAM → OAM 的因果鏈；`0x080baef0` 仍是 staging candidate，附近 `0x081869c8` descriptor table（含 `0x080baef1` Thumb pointer）是下一個最小 indirect-dispatch 追蹤點。不得以 queue resource pointers 或畫面 OCR 代替 source table。
- [ ] 取得實際 glyph writer 的 ROM pointer／RAM table／code-unit argument；確認 1–3 個重複 glyph 的 source hash、transform 與 OBJ tile hash 後，才可開始建立 stable string ID、codepage 或翻譯批次。

## M1.7：descriptor selector／indirect dispatch 有界追蹤

- [x] 解析 `0x080ba8d8` selector 的 ARM7TDMI Thumb boundary、embedded literal pools、三個 direct BL callers 與 group/index 參數；確認 `0x08182b70` 是 `0x08182b54[7]`，value 為 `0x081869c8`。
- [x] 解析 callback table `0x0815eeec` 的 25×8 dispatch、`opcode << 3` 選擇與 `0x0815cccc` trampoline；descriptor bounded window 為 620 bytes／155 words、6 sentinel、variable-length command stream，不宣稱 fixed record stride。
- [x] 記錄 descriptor function-pointer refs：`0x080baef1` 1 次、`0x080bafb9` 4 次；callback payload advance 只採用由 cursor/progress 反組譯交叉得到的欄位，沒有把未解 state/header 猜成 source table。
- [x] natural A/Start/方向鍵 transition（60 秒／38 KEYINPUT reads）有界陰性：三個 selector caller、selector entry、`0x080baef0`、`0x080bafb8`、`0x02001000` writer 均 0 hit；generic queue/LZ77 仍落在既有 resource path。
- [x] synthetic group=1/index=7 fallback 以 fail-closed PC/register override 驗證 `0x081869c8 → 0x080ad0fc(r0=descriptor,r1=0xffff)`；return guard 停止，不把 synthetic selection 當自然場景，不繼續 force-drain。
- [~] selector/descriptor 到真正 glyph writer 尚未接通；fresh boot `0x03006950` pointer 與 `0x0203db40` counter 都為 0，下一步應設 reset 前 write watch 找到 RAM selector-table initializer／state dispatcher，再以自然已初始化 table 觸發 caller。
- [ ] 取得 `0x080baef0`／`0x080bafb8` 的實際 source/index/code-unit argument，並交叉到 staging→OBJ VRAM→OAM；未完成前維持 source table、stable string ID、codepage 與翻譯封鎖。

## M1.8：selector table initializer 與 natural transition

- [x] fresh mGBA process 從 GDB 初始 `pc=0` 起點先 arm `0x03006950` pointer、相鄰 halfword、`0x0203db40` counter 與 KEYINPUT watches；沒有直接寫 selector table/state。
- [x] 對 `0x03006950` 做 aligned literal-load/store 與 bounded BL caller pass：157 word occurrences、165 literal refs、22 個 Thumb store candidates；候選與 function hash/width/callsite 分層記錄，未把 pattern ref 升格成 initializer。
- [x] 執行三條明確 natural transition cohort：`boot-start`、`fast-start`、`aggressive-start`；另以同一路徑 initializer-only hold/release follow-up 排除 full dispatch breakpoint budget 影響。每條保留 key/time/screen hash/hit count。
- [x] bounded negative：所有 cohort 的 selector pointer/counter write、三個 selector caller、selector entry、descriptor producer/callback 都是 0；watchpoint install failures 為 0。GDB `R` reset packet 的 `E07` 也已記錄，不能用同一 process replay reset。
- [~] initializer 尚未自然命名；`0x0812f2b4`、`0x0813e428`、`0x0813e574` 只列為 static priority candidates，下一步做 caller/source/state argument mapping，不再延長相同 reset→Start navigation。
- [ ] 取得自然 selector／descriptor consumer 與第一個 source/index/code-unit edge；未完成前維持 glyph source chain、source table、codepage、ledger、翻譯與回插封鎖。

## M1.9：selector state argument mapping

- [x] 以 metadata-only static tool 追 `0x0812f2b4`、`0x0813e184`、`0x0813e428`、`0x0813e574` 四個 priority Thumb functions；各自保留 prologue、bounded return candidates、256-byte function hash 與 direct BL caller count。
- [x] 對 `0x03006950`、`0x030068c0`、`0x030066b0`、`0x03005ca8`、`0x0203db40` 做 literal/store edge 解碼；確認 `0x0813e428` 的 selector swap、`0x0813e574` 的 RAM restore 與 `0x0812f2b4` 的 ROM literal branches。
- [x] 沿 direct caller 向上最多三層，記錄 callsite、Thumb boundary、caller hash/length 與 r0–r3 linear-provisional provenance；`0x080bee40`／`0x081534ae` 分別指向 provisional ROM table-derived arguments。
- [~] static provenance 尚非自然 runtime selector hit，也不是 glyph/source table；M1.8 的三組自然 negative window 保持不變，未新增 synthetic state。
- [ ] bounded map `0x08198a98`／`0x087df54c` table shape 及其 source writer，再取得可重抽取的 code-unit/glyph edge；未完成前維持 source table、codepage、ledger、翻譯與回插封鎖。

## M1.10：ROM pointer-table shape 與 bounded consumer

- [x] `0x08198a98` bounded 0x400-byte window 的 hash、word/pointer count、sentinel offsets `0x5c`／`0xa4` 與 variable-stream classification 已重抽取；未假設 fixed pointer stride。
- [x] `0x087df54c` 的第一個連續 pair run 已確認為 125 records、stride `0x8`、span `0x3e8`、99 unique even ROM data pointers；第一個 non-ROM pointer break 為 `0x3e8`。
- [x] 交叉到兩個實際 static reader：`0x080bee30` literal → `0x080bee40` selector swap，以及 `0x08153466` literal → `0x081534ae` selector swap；Thumb boundary/function hash 均保留。
- [x] 對前八個 `0x087df54c` unique target 做 0x80-byte hash/ROM-pointer/LZ77-header count；bounded window 沒有 LZ77 header 命中，但不把此陰性升格為全區未壓縮證明。
- [~] 兩個 table 都是 ROM-resident state/resource provenance，尚未建立 source writer、code-unit 或 glyph edge；不得建立翻譯 ledger。
- [ ] 追 `0x08198a98` variable consumer 與 `0x087df54c` data targets 的下一個可命名 source/class edge，再決定是否需要新的自然 runtime watch。

## M1.11：OAM／OBJ consumer 與 destination source-class mapping

- [x] 建立只追已知 OAM buffer、固定 `0x06013000` DMA 與 `0x06010000` literal references 的 bounded analyzer；不重跑同一 reset→Start negative、全 ROM glyph scan 或 source dump。
- [x] 以 Thumb boundary、literal pool、function window hash 與 direct BL caller 交叉驗證 `0x080a9af4` 的 DMA3 setup：`0x030033f0 → 0x07000000`、`0x84000100`、`0x080a9b26 → 0x080aabc8`。
- [x] 將 `0x080a9dd0`、`0x080a9e38`、`0x080a9ea8`、`0x080a9f04` 分層為 OAM table-fill、inline/fall-through、record append 與 object builder，保留 caller／RAM buffer 類別與 hash/count metadata。
- [x] 取得 `0x06010000` 的 12 個 bounded literal consumers，並交叉既有 8 個 `0x06013000` fixed-DMA patterns；報告不含 raw bytes、圖片、完整原文或 source table。
- [~] OAM 與 OBJ destination 仍只有 consumer/source-class 證據，沒有 source pointer → code-unit → glyph writer；不得建立 codepage、stable string ID 或翻譯 ledger。
- [ ] 從 12 個 OBJ-VRAM consumer 選一條自然可觸發 edge，取得 source register／ROM pointer／RAM table／code-unit provenance；若失敗，轉向下一個已命名 text/code-unit consumer。

## M1.12：OBJ source-class 與自然 runtime transition

- [x] 對 12 個 `0x06010000` literal-load PC 做 bounded Thumb DMA3 field decode；7 個 source/destination/control sequence confirmed，5 個 arithmetic/shared-control case 保持 unresolved。
- [x] 確認 static `0x02001000 → 0x06010000` 兩條 edge（`0x080bd136`、`0x0813efce`），並保留 `0x0200f874`、`0x02006000`、`0x081b13b8` 的 source class／control／length metadata。
- [x] 建立只讀自然 transition runtime probe：fresh process、單一 GDB connection、12 breakpoint、DMA3 SAD/DAD/CNT 與 KEYINPUT watch；不寫 selector/state/RAM payload。
- [~] 本回合 runtime listener 在 GDB attach 前受 socket／port 環境阻擋，沒有自然 hit 或 runtime negative；不得把 static source edge 升格成 glyph chain。
- [ ] 在 listener 可用時重跑同一 bounded probe，取得 source PC/LR/register、DMA edge 與畫面 hash；沿命中 caller 向上最多三層至 ROM pointer／RAM table／code-unit。

## M1.13：staging writer 與 resource record shape

- [x] 完整解析 `0x0813ef64` 的 Thumb boundary、34-byte window hash、incoming
  `r1`／`r2` data flow 與 `0x0815cafc` Huff → `0x0200afc8` → `0x0815cb00`
  LZ77-WRAM transform；未把輸入命名成文字。
- [x] 以精確 Thumb pointer `0x0813ef65` 建立 bounded record map：128 次
  occurrence、16 組、每組 8 筆、stride `0x18`、每筆 callback＋source pointer＋
  三個 bounded scalar fields；只輸出 hash、length、count 與 region metadata。
- [x] 交叉 `0x080bd0e0` resource initializer、`0x0813efb4` callback initializer、
  `0x080a9c40` registration target 與既知 `0x02001000 → 0x06010000` helper；
  記錄 ROM source pointer candidates 與 source marker `0x24`；當時仍保守不命名
  格式，後由 M1.15 bounded decoder 確認為 4-bit Huffman header。
- [x] M1.14 已找到這 16×8 candidates 所在 command stream 的 bounded reader：
  opcode `0x0c`、callback-table entry 12、source `+0x04` 與 argument `+0x08`；
  static source→staging chain 見 `research/m1.14-resource-reader-20260816.md`。
- [~] 仍沒有 natural runtime hit、code-unit、glyph identity 或文字用途；listener
  blocker 與遊戲 negative 分開記錄，未建立翻譯 ledger。
- [ ] 取得 reader 的實際參數並交叉 staging → OBJ VRAM → OAM；在此之前維持
  codepage、stable string ID、翻譯 ledger 與回插封鎖。

## M1.14：descriptor reader／source-index provenance

- [x] 解析 `0x0879243c` 8-entry state table、`0x0203b554` selector halfword、
  Thumb pointer `0x0813f22d` 與長 handler `0x0813f22c` 的 prologue／first
  return boundary／literal pool；確認 handler callsite `0x0813f242` 將
  `0x08794e24` 與 `0x0000ffff` 送入 `0x080ad0fc`。
- [x] 解析 queue drain 的 entry `+0x14` source／`+0x10` stream index、25×8
  callback table、opcode `0x0c` 的 handler `0x080ad3cc` 與 `BX r3` trampoline；
  確認 callback record `+0x04` → `r1` source pointer、`+0x08` → `r2` argument。
- [x] 對 128 次 `0x0813ef65` pointer 建立可重抽取 metadata：每次 preceding
  opcode `0x0c` match、16 組×8 callbacks、stride `0x18`、128/128 ROM source、
  `r2=0..7` 各 16 次；前三筆 source window 僅保留 hash/length/address。
- [x] 將前三筆 bounded source links 接到 writer `0x0813ef64` 的
  Huff→LZ77 staging expression；`r2=0` 可與 M1.12 `0x02001000 → 0x06010000`
  static edge 對接，但未宣稱畫面 glyph identity。
- [~] static source/staging provenance 已確認，natural runtime capture 仍受
  listener blocker；沒有 code-unit、string ID、Unicode identity、控制碼或
  字寬，故 source table、codepage、ledger 與翻譯仍封鎖。
- [ ] listener 恢復後只重跑同一條單一路徑，記錄 PC/LR、r1/r2、source/staging
  hash 與 DMA/OAM consumer；若仍無文字 identity，對 `0x087a*` source class
  做 bounded decoder，不再擴大全 ROM glyph scan。

## M1.15：nested Huff/LZ77 source class decoder

- [x] 只重放 M1.14 已確認的 `0x0813ef65` 16×8、128 筆 ROM source pointer；不做
  全 ROM glyph pattern scan，不讀取未命名的其他 source region。
- [x] 以本作工具重現 mGBA BIOS 的 GBA Huffman tree walk：128/128 header 是
  `0x24`（4-bit），tree／stream boundary、consumed span、output length 與 hash
  均可重抽取；decoder 有 synthetic 4-bit round-trip 測試。
- [x] 以 Huff output 作 LZ77 input：128/128 都是有效 `0x10` stream，最終 output
  皆為 `0x1000` bytes、128 個完整 4bpp tile block；只保留 hash、長度、entropy、
  zero/FF count、tile count 與 unique hash count。
- [~] 這批資料現可命名為 resource payload／staging-bank input class，與
  `r2=0..7` 的 bank expression 相容；仍不能命名為文字、code-unit 或 glyph，
  122 個 unique output hash 也不等於 122 個字元。
- [ ] listener 恢復後，以同一路徑驗證自然 transition 是否真的把某一 bank
  搬到 OBJ VRAM；若畫面仍只消費 resource asset，轉向尚未命名的 text/code-unit
  consumer。source table、codepage、ledger 與翻譯仍封鎖。

## M1.16：命名 resource 與實際 OBJ frame 交叉

- [x] 只重放 M1.14 已確認的 `0x0813ef65` 16×8／128 筆 source records；不擴張
  source set、不做全 ROM glyph scan、不輸出 raw payload、capture 或圖片。
- [x] 以 M1.15 decoder 將 128/128 `0x24` Huff → `0x10` LZ77 payload 留在工具
  記憶體，與 hash 固定的 Start-screen VRAM/OAM capture 交叉；capture 為 46 個
  active sprite、84 個 unique tile、184 個 tile occurrences。
- [x] 32-byte aligned exact sprite 與 hflip/vflip/rotate180/nibble-swap 變形均
  0 hit；非零 tile 為 0/173 occurrences、0 個 unique non-zero tile hit。11 個
  空白 tile occurrences 分開保留，不能被誤讀成文字證據。
- [~] 這只證明「本次 capture 中，命名 resource set 不是直接 OBJ source」；不能
  因此把 resource 全域分類成非文字，也沒有得到 code-unit、glyph identity 或
  Unicode。
- [x] 由已知 consumer 的靜態 caller/literal 線索轉入 M1.17 命名 text/code-unit
  reader；source table、codepage、ledger、翻譯與回插仍封鎖。

## M1.17：第一條命名文字／code-unit consumer edge

- [x] 確認 ROM table base `0x08163444`、`index * 0x0a` addressing、object field
  `+0x24` 的 index 來源，以及 `0x080b6460` 的 Thumb boundary/literal pool。
- [x] 確認 reader 以 `ldrb` 消費 byte unit、在 `0x20` sentinel 停止，並以
  `0x080b64e4` 的 Thumb BL 將固定 descriptor pointer `0x08163638` 送至
  `0x080aa1f4`；function end/return candidate 與 literal load 交叉驗證。
- [x] 只對 table 起點前 37 筆、每筆 10 bytes 的 ASCII/padding-class prefix 做
  metadata-only 重抽取；不提交 raw bytes、完整原文或 decoded strings。
- [~] 這是第一個 confirmed code-unit edge，但 bounded prefix 暫時只屬 UI/map-label
  class；`0x080aa1f4` 仍是 OAM record writer candidate，未確認 glyph identity、
  日文主劇情 source、codepage、control codes 或 staging→OBJ chain。
- [ ] 沿 reader family 找到日文主文字的 table/category mapping、source/index、
  codepage、控制碼與長度規則；在此之前不得建立 translation ledger 或回插資料。

## M1.18：16-bit code-unit、font bank 與 bounded source pointer table

- [x] 沿 `0x080ac3ac`／`0x080ac334` 完整確認 `ldrh`、16-bit unit、每 unit
  `+2` bytes、`0x0300` line-break branch 與 `0x0301` terminator；保留 ARM7TDMI
  function boundary、literal pool 與 hash metadata。
- [x] 確認 `0x080abf24` 的 font staging edge：code-unit high byte 選取
  `0x0815ed88` 的 `0x08`-stride bank pointer，low byte 使用
  `((low >> 4) << 10) + ((low & 0x0f) << 5)`，輸出至 bounded EWRAM scratch
  `0x020391e0`／`0x020395e0`，再經 `0x0815ee18` descriptor 進入 OAM writer family。
- [x] 以 `0x080dd884` 的實際 pointer load／callsite 交叉確認
  `0x085861c8 + signed_object_field_0x02 * 0x08 + 0x04`；只審核 28 筆 bounded
  prefix，record ID 1–28、stride `0x08`、ROM pointer 與每筆 `0x0301` termination
  均可重抽取，僅提交 hash／length／address／unit-class/control count。
- [~] 28 筆是第一個 bounded Japanese encoded-string candidate，但 category
  semantics、scene-to-record selection、Unicode identity 與完整主劇情／惡魔／
  技能／道具表仍未知；font-bank 是 addressing evidence，不是已解出的 codepage。
- [ ] 從 reader family 的自然 caller／RAM buffer 建立可命名 category boundary、
  stable source ID 與 codepage/control/width contract；未完成前不得建立 ledger、
  翻譯或回插資料。

## M1.19：source-table family 與自然 category mapping

- [x] 對 `0x080ac334`／`0x080ac3ac` 直接 callers 各做一次 bounded static mapping，
  以 64-callsite cap 保留 direct BL caller、function boundary/hash、r0 setup
  candidate 與最多三層 caller edge；
  只沿 caller 向上 1–3 層至 ROM pointer、RAM table 或 code-unit/index 參數；不重做
  M1.15 resource classification、OBJ hash 或全 ROM glyph scan。
- [~] 以最多三個可重現的自然 scene／object transition 交叉 caller state、source
  pointer／index、reader entry 與 terminator／line-break metadata；runtime 若受
  GDB listener 阻擋，已把既有 socket failure 與 static evidence 分開，沒有以
  synthetic state 代替自然命中。
- [~] 明確分離 28 筆 candidate 與 main/event、demon、skill、item、system data
  families；每一族只保留 bounded record count、stride／pointer rule、hash、length、
  control counts 與可回讀地址，不提交 raw source 或完整原文。目前新增確認
  `0x08162b0c`–`0x08162c26` 的 15 筆 zero-terminated inline family，但 category
  語意仍 provisional。
- [ ] 只有在至少一族的 source table、stable ID、code-unit/codepage、control code
  與 width rule 可重抽取後，才解除 M2 ledger gate；否則維持 blocked 並記錄最小缺口。

## M1.20：自然 caller state 與 category boundary

- [x] 從一個已確認的 direct caller 反組譯 object/state field、ROM literal 或 RAM
  pointer 的實際選擇；沿向上最多三層直到可命名的 source/index，而不是把 pointer
  形狀當語意。`0x080b52c4` 的 `+0x24`／`+0x14`／`+0x0c`、五筆 jump table 與
  15 筆 inline route 已以 Thumb load／boundary 交叉驗證。
- [~] 若 GDB listener 恢復，使用 fresh process、單一 connection 與最多三個自然
  transition 交叉 reader entry、source pointer、terminator／line-break metadata；
  目前仍受既有 socket blocker，保留精確環境陰性並以 static source boundary
  繼續，未寫 selector/table/state。
- [x] 至少為一個 family 建立 bounded addressing contract，分開 code-unit identity、
  control code 與 route metadata；
  Unicode identity 未確認前不建立翻譯 ledger。
- [ ] 將 route 與自然 scene/category 交叉並建立可審核的 stable source ID；在
  Unicode identity、width rule 與回插契約確認前不建立翻譯 ledger。

## M2：可審核翻譯 ledger

- [ ] 先完成日文 source table 與 stable string ID，再建立第一個有限 UI／事件批次。
- [ ] 專有名詞先查 Wikipedia zh-tw、巴哈姆特及其他獨立社群來源，建立 `zh-TW` 術語表與來源紀錄。
- [ ] 以 `restore_translations.rb` 產生本機工作記錄，保留來源 hash、控制碼與寬度預算。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的提交 ledger，通過 schema 與 repository safety 檢查。

## M3：回插與 QA

- [ ] 建立本作專用 encoder、字庫與回插器。
- [ ] clean ROM → 重建 ROM → 重新抽取，確認未修改內容一致。
- [ ] 產生／套用 BPS 並完成 byte-for-byte round trip。
- [ ] 在 mGBA 驗證已翻譯場景；未測畫面、字寬、控制碼與存檔風險都要明列。

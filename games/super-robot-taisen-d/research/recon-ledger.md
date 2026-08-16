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
啟動器基礎設施放進遊戲目錄。`tools/gdbstub_client.py` 與
`tools/runtime_memory_probe.py` 只提供可重跑的 GDB／記憶體讀取介面，probe 輸出
不傾印原文。

| 檢查 | 結果 | 可支持的結論 | 明確限制 |
| --- | --- | --- | --- |
| ROM entry breakpoint `Z1,080000c0,4` | `S05k`；`pc=0x080000c0`、`lr=0x08000000` | emulated CPU 確實進入 A6SJ ROM reset code | 不是文字或字型 renderer 命中 |
| VRAM write watchpoint `Z2,06000000,4` | `T05watch:06000000;`；停止點 `pc=0x00000264`，`r1=0x06000000` | runtime 確實觸發一個寫入 VRAM 的圖形 transfer 邊界 | 只能作 graphics consumer 陽性證據；尚未證明來源是字型 |
| 靜態池首字 read watchpoint `Z3,08076000,4` | reset 後 bounded `10 s` 無命中，GDB client timeout | 在這個 boot window 沒有讀取池首 4 bytes | 不能推論整個池或其他字串沒有被讀取 |

上表的第一、二列是 runtime 陽性邊界，第三個有效檢查是文字池首字的 bounded 陰性
結果；它們合在一起只證明「ROM 執行到圖形初始化／transfer，且該時窗未讀池首」，
不證明文字 renderer、decoder、glyph addressing 或 glyph identity。這個里程碑因此
定名為**靜態文字池／實際 pointer／bounded runtime 邊界**，不是文字消費者已完成。
本輪停止擴張 runtime port 基礎設施；後續若需要，應先以反組譯與 pointer caller
分類縮小 renderer 候選，再開新的獨立 session。

### 第一輪結論

| 問題 | 狀態 |
| --- | --- |
| ROM 身分／CRC | 已確認（A6SJ／`efb45117`） |
| 有界靜態文字池／分區線索 | 已確認 `0x076000..0x082490` 的 NUL 結尾 Shift-JIS 候選池；完整文本仍未確認 |
| 字型／glyph addressing | 未確認；尚未從 VRAM／ROM 做 byte-identical 來源匹配 |
| glyph identity | 未開始；字符表候選不能直接視為已知 codepage |
| codepage | 已確認有界靜態池使用嚴格標準 Shift-JIS；池外文本未確認 |
| 指標表 | 有界池已有 4-byte 絕對 pointer 命中與群組；語意／caller／runtime 未確認 |
| runtime 邊界 | ROM entry／VRAM transfer 有陽性；`0x08076000` 首字 read watchpoint 在 10 秒 boot window 陰性 |
| 壓縮 | 只有 BIOS／簽章候選，未確認與文本相關 |
| 控制碼／終止碼／行寬 | 未確認 |
| 可逆回插 | 未確認，尚未建立 encoder／builder |
| 翻譯 | 未開始 |

## 下一輪入口

1. 分類有界文字池的 pointer 群組與 ID／表格語意，確認名稱／UI 與話間資料的
   邊界是否共享同一 renderer。
2. 反組譯與 runtime 追蹤表格／字型 loader，優先確認兩個字符表是否會被讀入
   VRAM／RAM，以及字串 renderer 的來源參數。
3. 若靜態分析無法縮小範圍，啟動新的 mGBA GDB session，讀取 `DISPCNT`、VRAM、
   palette 與可疑 ROM／RAM 區域；每次 GDB 斷線都重啟 mGBA。
4. 只在取得一組可重複的字串邊界、codepage／控制碼與 glyph 來源後，才輸出
   `research/super-robot-taisen-d-decoded.jsonl` 並建立第一批翻譯。

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
| 終止與排版 | `confirmed-static / provisional` | 多個候選字串以 `0x00` 結束，觀察到 `0x0a` LF、全形空白 `81 40` | 最大行寬、游標語意、續行規則尚未驗證 |
| 控制／格式 | `provisional-static` | 觀察到 `ESC C6 %s` 候選序列與 `%s`／`%d`／`%u`／`%%` 參數 | `ESC C6` 是否為遊戲控制碼、參數消費規則和插入限制尚未證實 |
| pointer width／形態 | `confirmed-static` | 32-bit little-endian absolute GBA ROM pointers；target = `0x08000000 + file offset` 的表格可重跑 | 不是所有 aligned pointer 都是文本；事件／map struct 仍需 code-flow 核對 |
| pointer table A | `confirmed-static / text-candidate` | file `0x0cbc54`, 183 entries；149 unique targets；target `0x075a80–0x077100` | 表尾後的其他 entries 與資料結構尚未完整命名 |
| pointer table B | `confirmed-static / text-candidate` | file `0x0d1ffc`, 44 entries；26 unique targets；target `0x078528–0x0786fc` | 需以執行期選單／戰鬥畫面核對 |
| pointer table C | `confirmed-static / text-candidate` | file `0x0d20d8`, 4 entries；4 unique targets；target `0x07880c–0x078848` | 需核對其所屬畫面／事件 |
| pointer table D | `confirmed-static / text-candidate` | file `0x0d4d00`, 28 entries；16 unique targets；target `0x079764–0x0797e4` | 鄰接欄位含非 pointer 小資料，不能整段當純文字表 |
| runtime execution | `confirmed-runtime / bounded` | 獨立 headless mGBA/GDB session 可連線；continue 後 PC `0x03004d74`、SP `0x03007d64`、CPSR `0x8000001f`；ROM／IWRAM／VRAM 可讀 | 沒有完成穩定畫面導航、文字呼叫 breakpoint 或 glyph identity 核對 |
| VRAM／DMA | `confirmed-runtime / bounded` | 觀察到 DMA 將 ROM／IWRAM/EWRAM 資料搬往 VRAM，包含 `0x08079a08 -> 0x03004ee0` 與 `0x020013d8 -> 0x06000000` 類事件；VRAM read 非空 | 這只能證明執行期圖形資料活動，不證明某段就是字型或文字 tile |
| 字型資料 | `unmapped` | 看到 VRAM 活動，但未定位 ROM font、runtime glyph pool 或 tilemap identity | 需要畫面／字型候選與渲染路徑交叉驗證 |
| compression | `not-confirmed` | bounded signature scan 僅得到 noisy counts：LZ77 `10744`、Huffman `6692`、RLE `4704`、Diff `4966` | 沒有把任何 signature 當成文本壓縮；需由 code／runtime 呼叫證實 |
| 可逆回插 | `blocked-on-structure` | 目前只有 metadata／pointer summary tool，無 decoder／encoder | 先固定字串 ID、長度、控制碼、字型與 pointer relocation，再做未修改 round trip |
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

## 後續證據邊界

1. 用 ROM-independent tests 保持 identity／pointer summary 工具可重跑。
2. 若重新做 runtime，使用本 session 自己的 mGBA 進程與獨立 GDB port；只記錄寄存器、DMA、VRAM／IWRAM 範圍和可重現 breakpoint，不提交 build、probe 或 ROM。
3. 只有在同一候選字串能以 pointer／code-flow／畫面三者交叉確認後，才建立本機 ignored decoded source table。
4. 只有未修改內容可抽出、回插、再抽出逐 byte 一致，才將 reversible insertion 從 `blocked-on-structure` 改為 confirmed。
5. 第一批翻譯仍必須通過 `core/ledger/restore_translations.rb`、`strip_translations.rb`、schema、安全檢查與術語來源審核。

## 尚未採用的假設

- 不假設沿用黃金太陽、光明之魂或其他 GBA 遊戲的字型、壓縮、指標、控制碼或回插格式。
- 不把公開攻略、英文／中文 patch 或 static Shift-JIS 命中當成正式逐句翻譯來源。
- 不因 header complement mismatch 自動修補 ROM，也不將它改寫成「clean」版本。
- 不把 `B3EJ` 產品代碼單獨當成 ROM 身分；本帳以 header、大小和 hash 一起核對。

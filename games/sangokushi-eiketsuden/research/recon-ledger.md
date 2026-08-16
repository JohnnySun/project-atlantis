# 《三國志英傑伝》唯讀偵察帳

## 基本邊界

- 遊戲 slug：`sangokushi-eiketsuden`
- 目標版本：日版 GBA；候選產品代碼 `B3EJ`
- 本帳只記錄工程偵察和證據狀態，不保存 ROM、完整原始腳本、字型 dump、OCR 圖片或大段外部攻略原文。
- 《三國志孔明伝》不在本帳範圍內。
- 建立日期：2026-08-16（Asia/Taipei）

## 證據矩陣

| 項目 | 狀態 | 已有證據 | 仍需做的唯讀檢查 |
|---|---|---|---|
| 公開產品候選 | confirmed-public / not-ROM-confirmed | 公開資料將 GBA 商品列為 `AGB-P-B3EJ`；見 `term-sources.md` | 以 ROM header、檔案大小、雜湊確認實際 dump |
| ROM 檔案位置 | blocked | 本機工作區、常用下載目錄和掛載卷未找到 B3EJ／《英傑傳》檔案；委派來源主機 SSH 因認證失敗 | 由使用者提供或掛載合法自有日版 dump；不得從網路下載 ROM |
| ROM header | pending | 無 ROM 可讀 | title、game code、maker、revision、補數校驗 |
| CRC／雜湊 | pending | 無 ROM 可讀 | CRC32、MD5、SHA-1、SHA-256 |
| 文本儲存區 | pending | 未做二進位掃描 | 標準 Shift-JIS、客製 codepage、池／指標、壓縮 |
| 字型資料 | pending | 未做二進位或執行期觀察 | ROM 字型、VRAM 搬移、tile／tilemap、glyph identity |
| 控制碼／換行 | pending | 未讀到日版原文 | 終止符、游標控制、換行、事件參數、長度限制 |
| 可逆回插 | pending | 沒有 decoder／encoder | 未修改資料 round trip、重抽取與 BPS QA |
| 翻譯 ledger | ready / empty | 已決定使用 core ledger；本遊戲尚無原文表和翻譯記錄 | ROM decoder 產生 source table 後再建立第一批 work／ledger |

## ROM 到位後的最小記錄格式

先記錄 ROM header 與雜湊，再逐項填寫以下欄位；任何「猜測」必須留在 `hypothesis`，不可寫進 confirmed 欄位：

```text
rom_path_local: <ignored local path>
product_code_candidate: B3EJ
header_title: <observed>
header_game_code: <observed>
header_maker_code: <observed>
header_revision: <observed>
size_bytes: <observed>
crc32: <observed>
md5: <observed>
sha1: <observed>
sha256: <observed>
decoder_version: <once decoder exists>
```

原文解碼成功後，輸出位置固定為本機忽略檔 `research/sangokushi-eiketsuden-decoded.jsonl`；每行使用 ledger 要求的 `string_id`、`locale`、`text`、`provenance`，並在 provenance 區分直接解碼、執行期核對、OCR 候選和未映射 glyph。原文不可複製到 `translations/` 或提交的 `review_notes`。

## 目前禁止的推論

在沒有 ROM 前，不推論本作沿用任何其他遊戲的 Shift-JIS、Huffman、指標寬度、字型表、控制碼或回插格式；也不把公開攻略上的戰役敘述當成 ROM 劇情原文。`B3EJ` 只表示產品候選，不能單獨證明 ROM revision、header game code 或 CRC。

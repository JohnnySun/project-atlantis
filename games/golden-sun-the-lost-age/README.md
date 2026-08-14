# 《黃金太陽 失落的時代》漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、舊中文版、抽出的原文及實驗構建只保存在本機，不進入 Git。

## 當前進度

- 日版 Rev.00 基準 ROM 的標頭與多種雜湊已校驗。
- 已定位日版文字的上下文 Huffman 樹、分塊指標和壓縮資料。
- 已無損抽取 **12,772 條**訊息的 12-bit 代碼序列，並建立涵蓋全部 152 個擴展字形的 provisional 日文碼表；全量解碼沒有未映射字符。
- 已找到一份本機既有中文版作為行為參考。它以美版 `AGFE01` 為基礎，重寫了解碼程式，不能作為日版可直接套用的補丁。
- 已用日版原字形和完整碼表確認首批系統訊息，建立 35 條 `zh-Hans`／`zh-TW` 可審核草稿。
- 已完成資料驅動的 `zh-TW` 技術試作：從翻譯 JSONL 重建全套 Huffman 資料、加入 125 個繁體中文字形，並替換 35 條訊息。
- 試作 ROM 已在 mGBA 0.10.5 成功開機至標誌與姓名輸入畫面；這只是管線驗證，**不是完整翻譯**。

## 日版文字佈局

| 項目 | ROM offset |
| --- | ---: |
| Huffman 上下文指標入口 | `0x064C3C` |
| 字串分塊指標表 | `0x09CF40` |
| 第一段壓縮文字 | `0x064C4C` |
| 單位元組可變寬字形 | `0x05A8CC` |
| 日文擴展固定寬字形 | `0x05BF8C` |
| 字形圖層選擇表 | `0x05CDCC` |
| 字形渲染函式 | `0x03A890` |
| 訊息數 | `12,772` |

文字分成 50 組：前 49 組各 256 條，最後一組 228 條。

```sh
ruby ../../core/golden-sun/extract-huffman-text-ids.rb \
  --rom roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --output research/jp-text-ids.tsv \
  --count 12772 \
  --huffman-pointer-table 0x064c3c \
  --string-pointer-table 0x09cf40
```

日文碼表由 Apple Vision `.accurate` OCR、多句對齊投票、ROM 字形與 BDF 像素比對共同建立。OCR 只作候選證據；碼表仍標記為 provisional，便於後續逐字複核。完整本地解碼工作集可用下列命令重建，輸出已由 `.gitignore` 排除：

```sh
ruby ../../core/golden-sun/decode-text-ids.rb \
  --text-ids research/jp-text-ids.tsv \
  --codepage codepages/ja-extended.tsv \
  --output research/jp-decoded.jsonl
```

在 macOS 上需要重新產生 OCR 候選時，可先把 `render-original-text.rb` 的 PGM 輸出交給 Vision，再將結果與代碼序列對齊。這是研究輔助流程，不是正常構建的必要步驟：

```sh
swift tools/ocr_jp_text.swift research/jp-ocr-all/*.pgm > /tmp/gs2-jp-ocr.tsv
ruby tools/infer_ja_codepage.rb research/jp-text-ids.tsv /tmp/gs2-jp-ocr.tsv
```

推導器與正式解碼器共用 `core/golden-sun/japanese_codepage.rb`，避免兩份基礎假名映射產生分歧。投票結果仍須用原 ROM 字形人工複核後才能修改 `codepages/ja-extended.tsv`。

## `zh-TW` 技術試作

目前替換 35 條開機、存檔、資料繼承、難度選擇與姓名輸入訊息；以下列出代表項目，完整資料見 `translations/system-messages.draft.jsonl`：

| ID | 場景 | 試譯 |
| ---: | --- | --- |
| 0 | 無存檔資料 | `(沒有紀錄)`（保留原版 ASCII 括號） |
| 5 | 存檔損毀 | `部分資料已損毀，`／`無法正確復原。` |
| 6 | 從神殿復原 | `要嘗試從神殿`／`復原嗎？` |
| 10 | 遊玩時間標籤 | `遊戲時間` |
| 15 | 新遊戲姓名輸入 | `請輸入你的名字。` |
| 18 | 繼續遊戲 | `請選擇要繼續的紀錄。` |
| 32–33 | 寫入警告 | `處理完成前，請勿`／`關閉電源` |
| 36 | 前作資料繼承 | `要繼承前作《開啟的封印》的`／`通關資料嗎？` |
| 39 | 困難模式 | `要以困難模式開始嗎？`／`(怪物會變得更強)` |

構建器使用 Fusion Pixel Font 10px Monospaced `v2026.08.11` 的
`fusion-pixel-10px-monospaced-zh_hant.bdf`。`zh_hant` 是上游檔名；Atlantis 的輸出語種仍明確定義為 `zh-TW`，兩者不可混為未指定地區的通用繁體目標。

從專案根目錄執行：

```sh
ruby games/golden-sun-the-lost-age/tools/build_zh_tw_trial.rb \
  --rom games/golden-sun-the-lost-age/roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --text-ids games/golden-sun-the-lost-age/research/jp-text-ids.tsv \
  --codepage games/golden-sun-the-lost-age/codepages/ja-extended.tsv \
  --translations games/golden-sun-the-lost-age/translations/system-messages.draft.jsonl \
  --bdf games/golden-sun-the-lost-age/research/vendor/fusion-pixel-font-10px-monospaced-bdf-v2026.08.11/fusion-pixel-10px-monospaced-zh_hant.bdf \
  --output games/golden-sun-the-lost-age/roms/build/golden-sun-tla-zh-tw-trial.gba
```

目前的試作資料從 `0xF80000` 寫入 256,384 bytes，指標改為：

| 項目 | 新 GBA pointer | ROM offset |
| --- | ---: | ---: |
| 擴展字型 | `0x08F80000` | `0xF80000` |
| Huffman 表 | `0x08FBE7D8` | `0xFBE7D8` |
| 文字表 | `0x08FBE7F0` | `0xFBE7F0` |

新增字形 ID 已到 `0x214`，因此構建器實際產生了第三組上下文 Huffman 樹；通用抽取器可從三組樹完整反解全部 12,772 條訊息。

用通用 BPS 工具產生及重套補丁：

```sh
ruby core/patches/bps_create.rb BASE.gba TRIAL.gba TRIAL.bps
ruby core/patches/bps_apply.rb BASE.gba TRIAL.bps REAPPLIED.gba
```

本次可重現結果：

- 基準 CRC32：`830b795f`
- 試作 CRC32：`2e5132d5`
- BPS CRC32：`27bccf07`
- BPS 大小：258,440 bytes
- 試作與重套 ROM SHA-256：`518a722e3bcc55fe8026d31f6e0b9b253058260bcbbc55d658151094b1f93ff7`

用新指標重新抽取後，只有翻譯資料指定的 35 個 ID 不同；其餘 12,737 條訊息的 12-bit 代碼序列與來源 TSV 完全一致。構建器會先用碼表反解並核對每筆翻譯記錄的日文原文，避免人工辨識錯誤直接進入 ROM。

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。

詳見 [研究記錄](research/baseline-20260814.md)及[路線圖](ROADMAP.md)。Fusion Pixel Font 的來源與授權記錄見[共用字型說明](../../vendor/fonts/fusion-pixel-font/README.md)。

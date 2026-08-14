# 《黃金太陽 失落的時代》漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、舊中文版、抽出的原文及實驗構建只保存在本機，不進入 Git。

## 當前進度

- 日版 Rev.00 基準 ROM 的標頭與多種雜湊已校驗。
- 已定位日版文字的上下文 Huffman 樹、分塊指標和壓縮資料。
- 已無損抽取 **12,772 條**訊息的 12-bit 代碼序列；完整字形到 Unicode 的映射仍待完成。
- 已找到一份本機既有中文版作為行為參考。它以美版 `AGFE01` 為基礎，重寫了解碼程式，不能作為日版可直接套用的補丁。
- 已用日版原字形人工確認首批系統訊息，建立 3 條 `zh-Hans`／`zh-TW` 可審核草稿。
- 已完成首個可玩的 `zh-TW` 技術試作：重建全套 Huffman 資料、加入 15 個繁體中文字形，並替換兩條訊息。
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

## `zh-TW` 技術試作

目前只替換兩條訊息：

| ID | 場景 | 試譯 |
| ---: | --- | --- |
| 0 | 刪除存檔確認 | `(要刪除紀錄嗎？)`（保留原版 ASCII 括號） |
| 15 | 新遊戲姓名輸入 | `請輸入你的名字。` |

構建器使用 Fusion Pixel Font 10px Monospaced `v2026.08.11` 的
`fusion-pixel-10px-monospaced-zh_hant.bdf`。`zh_hant` 是上游檔名；Atlantis 的輸出語種仍明確定義為 `zh-TW`，兩者不可混為未指定地區的通用繁體目標。

從專案根目錄執行：

```sh
ruby games/golden-sun-the-lost-age/tools/build_zh_tw_trial.rb \
  --rom games/golden-sun-the-lost-age/roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --text-ids games/golden-sun-the-lost-age/research/jp-text-ids.tsv \
  --bdf games/golden-sun-the-lost-age/research/vendor/fusion-pixel-font-10px-monospaced-bdf-v2026.08.11/fusion-pixel-10px-monospaced-zh_hant.bdf \
  --output games/golden-sun-the-lost-age/roms/build/golden-sun-tla-zh-tw-trial.gba
```

目前的試作資料從 `0xF80000` 寫入 253,080 bytes，指標改為：

| 項目 | 新 GBA pointer | ROM offset |
| --- | ---: | ---: |
| 擴展字型 | `0x08F80000` | `0xF80000` |
| Huffman 表 | `0x08FBDAF8` | `0xFBDAF8` |
| 文字表 | `0x08FBDB08` | `0xFBDB08` |

用通用 BPS 工具產生及重套補丁：

```sh
ruby core/patches/bps_create.rb BASE.gba TRIAL.gba TRIAL.bps
ruby core/patches/bps_apply.rb BASE.gba TRIAL.bps REAPPLIED.gba
```

本次可重現結果：

- 基準 CRC32：`830b795f`
- 試作 CRC32：`e6fa4e92`
- BPS CRC32：`a36c5a20`
- BPS 大小：255,048 bytes
- 試作與重套 ROM SHA-256：`a2704e87235ecbc4ffa6f002e9b090c153fa3ecfcb938822aede4450fa0f9141`

用新指標重新抽取後，只有 ID 0 與 15 不同；其餘 12,770 條訊息的 12-bit 代碼序列與來源 TSV 完全一致。

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。

詳見 [研究記錄](research/baseline-20260814.md)及[路線圖](ROADMAP.md)。Fusion Pixel Font 的來源與授權記錄見[共用字型說明](../../vendor/fonts/fusion-pixel-font/README.md)。

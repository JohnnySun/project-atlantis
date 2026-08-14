# 《黃金太陽 失落的時代》漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、舊中文版、抽出的原文及實驗構建只保存在本機，不進入 Git。

## 當前進度

- 日版 Rev.00 基準 ROM 的標頭與多種雜湊已校驗。
- 已定位日版文字的上下文 Huffman 樹、分塊指標和壓縮資料。
- 已無損抽取 **12,772 條**訊息的 12-bit 代碼序列；字形到 Unicode 的映射仍待完成。
- 已找到一份本機既有中文版作為行為參考。它以美版 `AGFE01` 為基礎，重寫了解碼程式，不能作為日版可直接套用的補丁。
- 尚未產生可玩的中文構建；第一個目標是少量開場文字、中文字形和可逆 BPS 的端到端驗證。

## 日版文字佈局

| 項目 | ROM offset |
| --- | ---: |
| Huffman 上下文指標入口 | `0x064C3C` |
| 字串分塊指標表 | `0x09CF40` |
| 第一段壓縮文字 | `0x064C4C` |
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

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。

詳見 [研究記錄](research/baseline-20260814.md)及[路線圖](ROADMAP.md)。

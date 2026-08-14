# Golden Sun 共用工具

這裡保存《黃金太陽》GBA 兩作可共用、且不依賴商業 ROM 的研究工具。

## Huffman 文字 ID 抽取

`extract-huffman-text-ids.rb` 讀取遊戲使用的「以前一個字符為上下文」Huffman 格式，輸出每條訊息的 12-bit 代碼序列。它不把日文或其他區域碼頁轉成 Unicode，因此輸出適合做結構校驗和後續字形映射，不應視為可讀腳本。

抽取器支援長字串在長度表中使用一個或多個 `0xFF` 分段的原版格式。

```sh
ruby core/golden-sun/extract-huffman-text-ids.rb \
  --rom path/to/clean.gba \
  --output research/text-ids.tsv \
  --count MESSAGE_COUNT \
  --huffman-pointer-table 0xOFFSET \
  --string-pointer-table 0xOFFSET
```

輸出的遊戲文本屬於本地研究中間產物，已由 `.gitignore` 排除。

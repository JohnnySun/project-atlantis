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

## 日文碼表解碼

`japanese_codepage.rb` 定義兩作共用的單位元組日文區段，`decode-text-ids.rb` 再載入遊戲版本專屬的擴展碼表，將 12-bit TSV 轉為本地 JSONL 工作集。嚴格模式遇到未映射字符會立即停止，控制碼保留為 `{XX}`，`0x03` 轉成換行。

```sh
ruby core/golden-sun/decode-text-ids.rb \
  --text-ids research/text-ids.tsv \
  --codepage games/example/codepages/ja-extended.tsv \
  --output research/ja-decoded.jsonl
```

## 原版字形預覽

`render-original-glyphs.rb` 可把抽出的字符 ID 畫成聯絡表。預設偏移對應《失落的時代》日版 `AGFJ01` Rev.00；其他版本必須明確提供經過驗證的 `--single-font` 與 `--extended-font`。

```sh
ruby core/golden-sun/render-original-glyphs.rb \
  --rom path/to/clean.gba \
  --output research/glyphs.ppm \
  008d 0095 0104
```

`render-original-text.rb` 則把本地 TSV 中間產物逐句渲染為放大的 PGM，便於人工辨識。正式碼表必須用多條字串上下文交叉驗證，不能只依賴低解析度 OCR。

## 測試

上下文 Huffman 寫入器的回歸測試會確認原版兩組樹仍相容，並確認新增中文字形跨過 `0x1FF` 後會自動建立後續樹組：

```sh
ruby -e 'Dir["core/golden-sun/test/*_test.rb"].sort.each { |path| require File.expand_path(path) }'
```

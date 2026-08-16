# M3 glyph format receipt：two source planes to runtime cache

日期：2026-08-16（Asia/Taipei）

這是字型格式的 bounded static/runtime cross-check，不是字型 dump，也沒有把 raw glyph
bytes 寫入 Git。輸入 ROM 與 runtime report 只在 ignored／暫存路徑存在。

## confirmed

- 有效 Thumb span `0x080650DC–0x08065254` 的 glyph expander 每輪讀取兩組 source
  plane；每組按 codepage index 取 `0x20` bytes，迴圈 `0..31`，輸出 cache `0x80` bytes。
  source bases 是 `0x08232BCC` 與 `0x0822468C`，cache base 是 `0x02000000`。
- 第一 source plane 的每個 byte 以 bit `0x80,0x40,...,0x01` 分別 OR 入四個 output
  bytes 的低／高 nibble bit `0`／`4`；第二 plane 使用 `r2+2` 派生的兩個 selector
  masks。這是由逐指令 `ldrb`／`ands`／`orrs`／`strb` 路徑重現的 byte contract，
  不是由圖片或 OCR 反推。
- `tools/font_glyph_format.py` 已將此合成規則封裝成 hash-only verifier。B3EJ clean
  ROM 的 codepage index `1301`／code unit `0x9594`／selector `0`，靜態合成 cache
  SHA-256 為 `e56e457e233682a20ff319087d8d924d9e20da83830db08bdb75960ce27ca9f3`，
  與 patched B0 controlled runtime receipt 中 `0x02000000` 的 128-byte cache hash
  完全相同。這關閉了「source plane → cache bytes」的格式 edge；Unicode identity
  仍由 strict Shift-JIS `0x9594` → U+90E8 獨立確認。
- `tools/test_font_glyph_format.py` 的 3 個 ROM-independent tests 通過；工具只輸出
  codepage index、selector、長度、offset 和 hash，不輸出 glyph bytes、圖片或字型檔。

## provisional

- selector `0` 的 runtime receipt 已經交叉核對；其他 renderer selector 值的畫面語意、
  palette assignment 和兩組 source plane 的所有使用情境尚未完整枚舉。
- 這個 format 足以驗證未來「外部授權 glyph plane → game cache」的輸入格式，但沒有
  決定 custom Unicode 要使用哪個 raw code unit、哪個可安全重用的 codepage slot，或
  是否應擴充 table／font bank。任何 custom mapping 必須另有 source-usage、slot
  preservation 和 runtime receipt。

## pending／negative

- Table B withheld entry 的繁體 `經`／`驗` 仍無現有 codepage glyph；沒有用日文 `経`／`験`
  偷換。尚未提交任何未授權字型或 generated glyph bytes。
- 全遊戲 zh-TW 所需字集尚未建立；pool A/D 的 `將`、`歷`、`裝`、`碼` 等缺字與版面／
  控制碼契約仍需逐池處理。現有 format receipt 不等於 custom font insertion 已完成。

## 可重現命令

```text
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/sangokushi-eiketsuden/tools/font_glyph_format.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --index 1301 --selector 0 --output /private/tmp/b3ej-glyph-1301.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  games/sangokushi-eiketsuden/tools/test_font_glyph_format.py -v
```

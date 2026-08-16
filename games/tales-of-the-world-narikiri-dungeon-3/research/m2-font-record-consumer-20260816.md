# M2 source-pointer-shaped font consumer edge（2026-08-16）

## 固定 static chain

本回合追蹤的是另一個比 `0x08001414` 更接近文字來源的固定 code path，沒有做
新的 pointer scan，也沒有讀出或提交任何 source／glyph bytes。可重跑工具是
[`tools/font_record_consumer_probe.py`](../tools/font_record_consumer_probe.py)。

全 ROM 對 `0x080021A8` 的 direct Thumb BL 只有一處：file `0x015C26`。其 caller
在 `0x015C22` 先把 context 放入 `r0`，在 `0x015C24` 把保存於 `r8` 的 builder
input 放入 `r1`，接著呼叫 loader。更上游的 `0x08015B74` 只有一個 direct caller
`0x0CD170`；其 entry 以 `r8=r1` 保存 builder input。因此固定鏈是：

```text
object/text builder 0x080CD14C
  -> 0x080CD170 -> 0x08015B74 (r8 = builder input)
  -> 0x08015C26 (r1 = r8)
  -> 0x080021A8 ([r1], [r1+1])
  -> 0x080DDCC4 + sjis_like_index*0x20
```

`0x080021A8` 直接讀 `r1` 與 `r1+1`，以 lead `0x87` 為分界計算相同的
lead/trail index，再以 `lsls #5` 與 literal `0x080DDCC4` 選固定 32-byte
asset slot。這是 **source-pointer-shaped static edge**，不是 strict
`string_id` 的 runtime edge：`r1` 究竟指向哪一筆資料仍須在 live breakpoint
取得並對照五個 strict windows。

## lookup 初始化與輸出邊界

loader 內有固定 `0x08002100` init caller（全 ROM direct callsites 四處），其
固定 literals 指向 IWRAM `0x03001462`／`0x03001464`。目前能確認的是 initializer
會寫 lookup／palette-shaped bytes；實際值依 runtime 狀態，不能把 static table
bytes 當作 glyph identity。loader 的輸出是 caller context／中間 buffer-shaped
destination，尚未證明是 VRAM 或最終 tilemap。

## 分類

| 邊界 | 狀態 |
| --- | --- |
| `0x08015C26` 唯一 direct caller of `0x080021A8` | **confirmed-static** |
| builder input→`r8`→loader `r1` provenance | **confirmed-static register shape** |
| loader 兩 byte input read | **confirmed-static** |
| input bytes 是五窗 strict record | **unconfirmed** |
| live source read PC/LR、asset read、output buffer | **unconfirmed** |
| `0x080DDCC4` asset 的 glyph identity／完整 codepage | **provisional／unconfirmed** |
| width、capacity、pointer rewrite、VRAM、round-trip、BPS | **unconfirmed** |

## 下一個最小 runtime slice

在同一個本作獨立 mGBA session 只設 `0x080021A8` entry breakpoint；命中後記錄
`r0/r1/r2/lr`，對 `r1` 指向的固定 source read 設 bounded read-watch，並對
`0x080DDCC4 + computed_index*0x20` 設單一 ROM read-watch。若 source 位址落入
strict five-window，才保存 `string_id`、caller 與 asset receipt；否則照實記
non-strict／outside-window。不要把 `0x08001414` 的 static path 或畫面 OCR 當作
這條 live source edge。

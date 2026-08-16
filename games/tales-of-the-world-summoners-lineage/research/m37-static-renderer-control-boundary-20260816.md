# A9PJ M37 靜態文字 dispatch／控制碼邊界（2026-08-16）

## 範圍

本切片只重用既有 M20 runtime probe 與 M23 private raster，不掃描新的 pointer、
不建立新的 provisional overlay，也不建立劇情來源或翻譯 row。目標是把已知
`0x080063E0` consumer 的控制流分成「終止／換行／字型 record」三條路徑，並留下
一個可重跑的 metadata-only model。

## ROM／程式證據

| 項目 | 固定值 |
| --- | --- |
| ROM | A9PJ，SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| stream loop | bus `0x080063E0`，file span `0x63E0–0x6448`，span SHA-256 `c523e514745f264f9eb6c67a4ad6c861406ead0bc50a28322f7d32da5ed090e5` |
| record consumer | bus `0x080049A0`，file span `0x49A0–0x4DA4`，span SHA-256 `1390a44b9529f767e0bf6c65a3937da71b47943274aceee52664314175ddd3fd` |
| record geometry | `0x08089E00 + code_unit * 0x18`，16-bit little-endian unit |

對 `0x080063E0` 的固定 Thumb path：先在 `0x08006404` 檢查 `0x0000`；非零值再
在 `0x0800640C` 分支 `0xFF70` line-advance。其他非零 unit 走
`0x080049A0`，由該 consumer 依 `unit * 0x18` 讀取 font record。這只證明 dispatch
與 addressing；它不證明某個 unit 的 Unicode 身分，也不把所有非零 unit 命名為
可翻譯文字。

因此，`0x0003` 等曾在 M24/M27 output 顯示為 unresolved 的 unit，在這個 consumer
path 上應記為 `font-record-consumer`，而不是因為頻率或位置直接標成 control code。
其語意仍未確認。

## 固定 UI raster cross（不開 general ledger gate）

既有直接 caller `0x0801A2B0` 的 bounded stream `0x1FA35E` 經 M23 MSB-first
16×12 raster 渲染；stream（含 `0x0000`）SHA-256 為
`14cd36a8e720eab7232e23562bdae105d3c18c4c96e4f836f57d36b25877cf02`，private
render image SHA-256 為 `71d91f96745290b383a2beda737c0c7d076e5de55f4b1950e0ec42b3bb9b3d7c`。
這列的已知 row-0／row-1 kana anchor 使前後兩個 CJK record 可人工核對為
Unicode `U+6700` 與 `U+521D`；它們的 record SHA-256 分別為
`7bac120ee9e0233c4f31a58cdcbaa88e8aa513b77c9119255ecfafe792ad2b4f` 與
`3102818631279460cc8c667c30d33bf903ac622565159a19ee72b15bdc38c36ef0b`。
這是 bounded static-context mapping，沒有 runtime screen／reader receipt，故不
提升為 general codepage，也不增加 ledger eligible rows。

## Runtime 邊界與結果

本次只啟動本 session 的 A9PJ mGBA，使用既有硬編碼 `23901` build 與單一連線；
mGBA 在建立 socket 時回報 `Debugger: Couldn't open socket`，沒有產生 listener，
自己的進程已停止。其他 listener 的 ROM ownership 不屬於本作，未連線、未停止、
未把這次失敗解讀成文字 consumer negative。

| 欄位 | M37 結果 |
| --- | --- |
| static terminator `0x0000` | confirmed on caller branch |
| static line advance `0xFF70` | confirmed on caller branch；semantic 仍限 line advance |
| nonzero → record consumer | confirmed static path |
| general Japanese／CJK codepage | not confirmed |
| non-UI scene row | `0` |
| existing bounded ledger-eligible known-screen rows | `2`（M32/M34；未擴張） |
| runtime reader／caller hit in this slice | `0`，因 socket startup failure，非 path negative |

## 可重跑命令

程式 span 可用既有 `tools/disasm_code.py` 以 `--offset 0x63e0 --length 0x88`
及 `--offset 0x49a0 --length 0x404 --mode thumb` 重建；fixed UI raster 則使用
既有 `tools/m23_font_render.py` 對 `0x1FA35E` 輸出到 `/private/tmp`。新的
`static_render_path()` 與 summary metadata 在 `tools/m20_text_runtime_probe.py`，
純測試在 `tools/test_m20_text_runtime_probe.py`；tracked output 只有 hash／offset／
counts，沒有 ROM、raw stream 或圖片。

## 下一個最小缺口

需要一個可獨立驗證的 general Japanese／CJK mapping 或 control consumer，並且至少
要有一個非 UI scene role；在取得 fresh mGBA/GDB reader receipt 或等價的已知畫面
source→VRAM proof 前，不擴張 provisional rows、不建立完整 source table／翻譯
batch，也不宣稱 M1.8/M1.9 BG1 transfer 已完成。

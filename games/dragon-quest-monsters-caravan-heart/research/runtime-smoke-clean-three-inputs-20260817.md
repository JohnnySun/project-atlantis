# clean A9HJ runtime smoke：三次輸入與 title/logo（partial，2026-08-17）

這份 receipt 記錄本 session 自己啟動的 mGBA 與獨立 GDB listener 對 clean A9HJ 的唯讀
trace。它不是翻譯目標畫面 QA，也沒有把未命中的 glyph／layout breakpoint 填成 pass；沒有
寫入 ROM、save、RAM 或 VRAM。

## 可重現命令

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/trace_clean_loader.py \
  --port 63549 --baseline-seconds 1 --between-seconds 3 \
  --inject-a 3 --input-timeout 8
```

listener `63549` 只屬於本 session 的暫存 mGBA process；trace 結束後已停止該 process，
其他 mGBA listener 未被停止或覆寫。

## 結果

- clean ROM：size `8,388,608`、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- input sequence：三次 A，僅在 input consumer 的 `r0` 做暫存器覆寫 `0x03FE`；`KEYINPUT`
  readback 仍為 `0x03FF`，沒有寫 ROM／save
- 第一次資產搬移：ROM `0x0846EDCC` → VRAM `0x0600C000`，helper `e`，length `5438`，
  output SHA-256 `2B321A94134C6B81658CD04DD405190B97509A65DFE33CF93829016CD5FF7DC1`
- 第二次資產搬移：ROM `0x08601894` → VRAM `0x06010000`，helper `e`，length `1022`，
  output SHA-256 `1F36784228FF1CD7E1C5A7A18A9D9BC53F5F3521953B751EFF45BDC98888E01E`
- 第三次輸入後另命中多個 ROM→VRAM／EWRAM asset dispatch，最後 I/O 為
  `DISPCNT=0x1240`、`BG0CNT=0x1E08`、`BG1CNT=0x1F09`、`BG2CNT=0x1C02`、`BG3CNT=0x1D03`
- 第三次輸入後命中 clean `0x08012500` text-parser 18 次；沒有命中
  `0x0801266C`、`0x08013738`、`0x08013E00`、`0x08013E4C`
- `runtime_qa=partial`：已證明 clean title/logo 載入與 parser 可達，尚未進入可核對的目標
  menu／battle scene；glyph identity、字寬／VWF、控制碼與完整場景 QA 仍未完成

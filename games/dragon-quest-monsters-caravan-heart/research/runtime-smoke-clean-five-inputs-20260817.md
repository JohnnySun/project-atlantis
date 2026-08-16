# clean A9HJ runtime smoke：五次輸入與 menu-like tilemap（partial，2026-08-17）

這份 receipt 是同一 clean A9HJ／同一 session-only mGBA listener 的延長唯讀 trace；它
補充三次輸入 receipt，不是翻譯目標畫面 QA，也沒有把未命中的 glyph／layout breakpoint
填成 pass。

## 可重現命令

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/trace_clean_loader.py \
  --port 53006 --baseline-seconds 1 --between-seconds 2 \
  --inject-a 5 --input-timeout 8
```

listener `53006` 只屬於本 session 啟動的暫存 mGBA process；trace 結束後已停止該 process，
其他 mGBA listener 未被停止或覆寫。

## 結果

- clean ROM：size `8,388,608`、CRC32 `3C24ABCC`、SHA-256
  `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- input sequence：五次 A；每次只在 `0x08011D3C` input consumer 的暫停點覆寫 r0=`0x03FE`
- 第 3 次 A 後：`DISPCNT=0x1240`、`BG0CNT=0x1E08`、`BG1CNT=0x1F09`、
  `BG2CNT=0x1C02`、`BG3CNT=0x1D03`
- 第 4 次 A 後：`DISPCNT=0x1140`、`BG0CNT=0x1D0C`、其餘 BG control 為 0
- 第 5 次 A 後命中 clean `0x08012500` text-parser 12 次，呼叫時 `r1=0x0600F000`
- 全程沒有命中 `0x0801266C`、`0x08013738`、`0x08013E00`、`0x08013E4C`
- `KEYINPUT` readback 維持 `0x03FF`；沒有寫 ROM／save
- `runtime_qa=partial`：這只把 title/logo → menu-like tilemap → parser 的可達性固定下來，
  尚未證明 bounded 翻譯文字在穩定畫面上消費，也沒有新增 glyph identity、控制碼或 VWF 證據

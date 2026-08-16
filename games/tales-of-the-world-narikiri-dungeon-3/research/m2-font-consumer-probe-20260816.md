# M2 bounded font consumer harness（2026-08-16）

## 目的與界線

本回合建立 [`tools/font_consumer_probe.py`](../tools/font_consumer_probe.py)，
把下一次 runtime 回合縮到已確認的 `0x08001414` font-map entry。它不再掃
resolver／pointer，也不讀出 source 或 glyph bytes：只記錄 entry registers、
`r2` 推導出的 bounded asset slot、固定 transform entry、asset read-watch 與
`0x03000560` scratch write-watch 的 stop metadata。KEYINPUT 只用既有 core client
做短 bounded navigation。

固定算術是前一回合 `m2-font-pipeline` 的 confirmed-static contract：
`0x080DDCC4 + r2*0x20`。因此 harness 的 asset watch 是由已命中的 live register
計算出的單一地址，不是 pointer scan，也不會把高位 asset pointer 猜成文字表。

## Harness contract

1. 在 reset stop 只安裝 `0x08001414` breakpoint 與 KEYINPUT read-watch。
2. 命中 entry 後記錄 `r0/r1/r2/lr`；若 `lr` 對應固定 direct caller
   `0x08001556` 或 `0x080015F8`，標成 format-loop caller，否則保留 caller unknown。
3. 對 `0x080DDCC4 + r2*0x20` 安裝一次 ROM read-watch；同時只觀察
   `0x080011A8`／`0x080012E0` entry，最多 `max_stage_stops` 次。
4. asset read 命中後移除該 watch，對 `0x03000560` 安裝一次 bounded write-watch；
   只保留 stop、PC/LR/registers、stage 與 status。
5. 任一 stage timeout、unexpected stop 或 watchpoint install error 都照實輸出；
   不覆寫 state、object、save 或 ROM。

離線測試只驗證地址算術、固定 caller LR 與 metadata 不含 bytes；本回合沒有可用
mGBA socket，因此尚未產生 runtime hit。

## 狀態分類

| 證據 | 本回合狀態 |
| --- | --- |
| harness 使用 shared `core/gba` GDB client | **confirmed-static/tooling** |
| `0x08001414`→asset slot 的 live hit | **unconfirmed** |
| asset read／transform／scratch write 因果鏈 | **unconfirmed** |
| strict five-window record→parser source edge | **unconfirmed by design** |
| glyph identity、codepage、width、VRAM writer | **unconfirmed** |
| translation、capacity、round-trip、BPS | **unconfirmed** |

## Runtime negative

本 session 對已分配 `24387` 做唯讀連線時，sandbox 在 socket 建立階段回報
`PermissionError: Operation not permitted`；受限升權重試因 approval stream
disconnect 被拒。這只表示本機工具層目前無法執行 harness，不是遊戲流程的
negative result，也不應冒充 runtime hit。待獨立 mGBA/GDB 可用時，以同一條連線
先跑本 harness，再按結果決定下一個 decoder／VRAM slice。

可重跑命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/font_consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <本作獨立GDB-port> --sequence start:8,none:12,a:8,none:12 \
  --max-events 64 --max-font-hits 1 --max-stage-stops 8 \
  --output /private/tmp/tow-nd3-font-consumer.json
```

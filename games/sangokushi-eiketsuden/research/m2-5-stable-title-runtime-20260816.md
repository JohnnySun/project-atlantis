# M2.5 穩定標題畫面與自然輸入邊界

日期：2026-08-16（Asia/Taipei）。本切片只處理日版 B3EJ 的 runtime 時序與
Table-B natural gate，不建立《孔明傳》資料，不建立翻譯 batch，也不提交 ROM、完整
日文、runtime dump、圖片或 mGBA build。所有報告只保存於 ignored `/private/tmp/`；本檔
只保存 I/O、位址、計數、按鍵序列與 hash metadata。

## 結論摘要

| 分類 | 結論 |
|---|---|
| confirmed-runtime | 以共用 `core/gba` GDB client 對同一 fresh B3EJ mGBA process 做 10 個一秒窗口；startup I/O 依序經 `DISPCNT=0x0140`（第 1–4 秒）、`0x0440`（第 5–6 秒）、`0x0240`（第 7–8 秒），第 9–10 秒穩定為 title `0x1E40`，BG0–BG3 為 `0x1400/0x1501/0x1602/0x1703`。 |
| confirmed-runtime | 在穩定 title 後，另以 `0x0805CF62` breakpoint 交叉核對 KEYINPUT read-watchpoint：16 次 bounded input（`none×8/start×4/none×4`）中，START stop 後的 `r0` 在 breakpoint 讀回 `0x03F7`，release 讀回 `0x03FF`；這證明注入值進入 reviewed input routine，不寫 ROM、save、`r6` 或 event buffer。 |
| negative / bounded-natural | 兩條 fresh process、single-connection、settle `9.0s` 的 stable-title paths（`none:8,start:4,none:20`、`none:8,a:4,none:20`）各 32 個 input events；builder／consumer／formatter／writer／glyph pipeline 全為 `0`，VRAM before/after SHA-256 均為 `5bbfad1b1af4a2c63e69e169077325a5210a6dc65b1d8ac2067a52fe37cf7463`，自然 cohort 仍為 `0`。 |
| provisional | START／A 在此無視窗 input hook 下沒有離開 title；公開 GBA 操作指南將 START 描述為進入主選單，但這只能作為導航假設，不能取代本 ROM 的自然畫面收據。 |
| unknown | normal runtime table `0x02014E78` 的 sentinel/count、自然 event byte provenance、actual index `<44`、自然 B entry→formatter→glyph cache→VRAM/tilemap receipt，以及 E pool 的自然 writer receipt仍未取得。 |

## Readiness 與穩定畫面時序

每次 trace 都先以 `runtime_readiness.py` 核對自有 PID、絕對 ROM 路徑和 listener；修正
相對 ROM path 比對後，direct Qt mGBA 的 port `2345` readiness 通過。每個 process 只
建立一條 GDB connection，完成後只停止該次由本 session 啟動且命令列明確指向 B3EJ 的
process。第一次相對路徑啟動的 `process_matches_rom=false` 保留為 readiness negative，
沒有把 listener 存在誤當成 ready。

同一 fresh process 的一秒 I/O metadata 如下；沒有保存 VRAM/RAM bytes：

| elapsed window | `DISPCNT` | BG0/BG1/BG2/BG3 |
|---|---|---|
| 1–4 s | `0x0140` | `0x1D00/0x1E01/0x1F02/0x0000` |
| 5–6 s | `0x0440` | `0x1D00/0x1E01/0x1F02/0x0000` |
| 7–8 s | `0x0240` | `0x1D00/0x1E01/0x1F02/0x0000` |
| 9–10 s | `0x1E40` | `0x1400/0x1501/0x1602/0x1703` |

因此此前 `settle=0.25s` 與 `settle=1.0s` 的 title negative 只能說明 startup window
未到穩定 title；不能用來否證主選單自然可達。M2.5 改用 `settle=9.0s`，並將 stable
title 的 I/O 獨立列為 confirmed，不把 startup transitions 當成文字畫面。

## Stable-title natural paths

兩份 ignored reports 為 `/private/tmp/b3ej-m25-stable-title9-start.json` 與
`/private/tmp/b3ej-m25-stable-title9-a.json`。兩次均使用
`tools/trace_m2_runtime.py --pipeline --natural-events 32`；工具現在保存每個 stop 的
寄存器 snapshot、requested active-low value 與 derived active-high mask metadata，但不
保存 source text 或 memory dump。

| path | settle | sequence | settled I/O | final I/O | natural pipeline hits | VRAM delta |
|---|---:|---|---|---|---:|---|
| `stable-title-start` | 9.0 s | `none:8,start:4,none:20` | `DISPCNT=0x1E40`; `BG0..3=0x1400/0x1501/0x1602/0x1703` | `DISPCNT=0x1C40`; 同 BG 配置 | 0 | 0 changed bytes; hash unchanged |
| `stable-title-a` | 9.0 s | `none:8,a:4,none:20` | 同上 | `DISPCNT=0x1F40`; 同 BG 配置 | 0 | 0 changed bytes; hash unchanged |

兩條 path 的 `natural_reachability=not-observed`、`natural_index_gate_status=not-observed`。
由於沒有 builder 或 consumer stop，不能記錄 runtime table count，也不能宣稱 actual
index `<44`。這是 title-to-menu 的 bounded negative，不是全遊戲自然不可達證明。

## Input timing receipt

診斷只在自有 process 裡設 `KEYINPUT=0x04000130` read-watchpoint 與
`0x0805CF62` breakpoint。KEYINPUT stop 的 PC 是 `0x0805CF5E`，也就是
`ldrh r0,[r0]` 後、下一個 `eors r3,r0` 前；因此工具只覆寫目的暫存器 `r0`，
`pressed_mask()` 只作報告 metadata，不另寫 `r3`。每個 breakpoint stop 先 read registers，
再 single-step breakpoint instruction，避免重複命中。receipt 僅保存：

- `none`：requested `r0=0x03FF`，breakpoint `r0=0x03FF`；
- `start`：requested `r0=0x03F7`，breakpoint `r0=0x03F7`；
- release：回到 `r0=0x03FF`；
- 16/16 的 stop sequence 符合 `KEYINPUT → 0x0805CF62`。

這關閉了「GDB input write 沒有進入 reviewed CPU instruction」這個 harness 疑問，
但不等於 START／A 已被遊戲 title state 接受，也不等於 natural consumer reachability。

## Evidence boundary

- **confirmed**：B3EJ process/port readiness、startup→stable-title I/O 時序、title BG
  配置、KEYINPUT injection 到 input routine 的寄存器 receipt，以及兩條 stable-title
  path 的零 pipeline／零 VRAM delta。
- **provisional**：公開操作資料支持將 START 視為主選單候選；這只協助導航假設，不是
  本 ROM 的 screen identity 或翻譯來源。
- **negative**：本切片沒有自然 builder／consumer／formatter／glyph hit，沒有自然
  index cohort，沒有自然 count `<44`，沒有自然 B/E record 到 VRAM receipt。
- **unknown**：要取得自然 cohort，下一個安全入口應是 static state gate
  `r4+0x14` 的 owner／menu-battle initializer，或已知畫面資料交叉證據；不再重複
  title-only KEYINPUT loop，也不擴大 controlled call。

因此 M2.4 的 unchecked natural index gate 保持 unchecked；M2.5 只完成可審核的
runtime boundary／negative，沒有把 controlled M2.3 receipt升格成自然證據。

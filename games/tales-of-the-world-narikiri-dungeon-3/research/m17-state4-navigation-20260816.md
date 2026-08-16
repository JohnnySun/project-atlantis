# M1.7 state 4 正常導覽邊界（2026-08-16）

本回合只處理 B3TJ 的 state dispatcher、state 4 初始化與正常 KEYINPUT
路徑；沒有擴充 resolver、沒有做新的 pointer scan，也沒有覆寫 state bytes、
save flags 或 resource object。ROM 身分仍是 `TOWNARIKIRI3`／`B3TJ`、16 MiB、
CRC32 `1867CCEF`。所有 mGBA raw state、save、RAM/VRAM dump 與 JSON capture
留在 `/private/tmp`，不屬於本文件的提交內容。

## 1. confirmed static dispatcher

主迴圈在 `0x08005E00` 依序呼叫 input/task/render 更新，再於
`0x08005E0E` 反覆呼叫 `0x08005ECC`；共用 return breakpoint 是
`0x08005E12`。`0x08005ECC` 的已確認行為如下：

1. 從 `0x02000000`、`0x02000001`、`0x02000002` 讀取 next/current/previous
   state bytes，先把 current 複製到 previous，再把 next 複製到 current。
2. 對新的 next byte 做 signed `ldrsb`，以 `index * 4` 索引 dispatch table
   `0x08741D94`；probe 只接受 `0..31`，不會把負值轉成掃描範圍。
3. 讀取單一 table entry，經 `0x080DD828` trampoline 呼叫 resolved Thumb
   function，然後回到 `0x08005E12`。

state 4 entry 是 table entry `0x08741DA4`，其 function word 為
`0x08009C69`（Thumb 對齊入口 `0x08009C68`）。state 0 handler
`0x0800A5BC` 會以 `0x08005E44` 寫入 next state `4`，所以 boot → state 4
是正常程式流程，不是 runtime state override。`tools/state_probe.py` 只在
mGBA reset stop 時先安裝 dispatcher entry/return breakpoint，避免錯過這個
one-shot boot handoff；報告會保留 entry 的 bytes、signed index、table entry、
resolved function 與 LR。

## 2. confirmed state 4 static conditions

state 4 handler `0x08009C68` 的實際短鏈是：

```text
0x08009C68 → 0x0800A58C → 0x0800A388 → 0x080004EC
```

`0x0800A388` 完成資源初始化後呼叫 `0x0800A2C0`。`A2C0` 對 resource
object 的 `+0x54` 做 bounded switch：狀態 `1`、`2`、`3` 才回傳成功 `1`；
其他值（包括初始化中的值）回傳 `0`，使 `A388` 回到 `0x0800A3DE` 重做
更新／檢查。成功後才會離開 state 4 handler，抵達共同 return site。

正常輸入的 static edge 也已確認：

- `0x08000E0C` 從 `0x04000130` 讀 KEYINPUT，目的暫存器是 `r1`，並把
  active-low 的按鍵邊緣寫到 IWRAM `0x030033F8`。
- `0x0800A1AC` 是 `A388` 內的 resource update caller；它檢查該 edge flag
  的 bit 0（A 鍵），成立後才把 table-derived signed byte 寫到 object
  `+0x54`，接著讓 `A2C0` 有機會返回成功。
- 因此此回合可重現的正常下一步是「在 live `A1AC` 邊界後送一次真實 A
  KEYINPUT read」，不是寫入 `0x02000000`、`+0x54` 或任何 state flag。

`A58C` 內含固定的 VRAM/resource setup 及 frame wait；這是 boot 初始化成本，
不能把停在該函式內解讀成已進入文字 menu/event。

## 3. runtime receipt and boundaries

### confirmed-runtime

- 獨立 mGBA/GDB session 在 reset stop 安裝 dispatcher entry/return 與
  `0x04000130` read watchpoint；KEYINPUT watch stop 顯示讀取後目的地為 `r1`。
- state probe 的 bounded sequences 都正常命中 boot `next=0x04` 的 dispatcher
  entry，resolved function 是 `0x08009C69`。較長的
  `start:1,none:300,a:1,none:300` 回合共 602 個 KEYINPUT events、603 stops，
  只有一個未完成的 state 4 dispatch entry，`dispatch_count=0`、
  `transition_count=0`。
- 另一個不帶高頻 input watch 的精確 call-path 回合依序命中
  `state dispatcher → 0x08009C68 → A58C → A388`；在後續 bounded 等待內
  未命中 `A2C0`、`A3F0` 或共同 return。這確認 state 4 的正常 setup caller
  會走到 `A388`，但尚未確認 state 4 leave。
- `state_probe.py` 現在在序列耗盡而 handler 尚未 return 時輸出
  `open_dispatch.return_observed=false`，避免把 partial receipt 誤報成
  transition。畫面只以 VRAM/palette/OAM SHA-256、長度與 non-zero count
  保存 metadata，沒有保存畫面或 RAM bytes。

### provisional-runtime

- 一次以 live `A1AC` entry 作為觸發點的 bounded harness 已走到「下一次
  KEYINPUT read 注入 A」分支，但 GDB stop 上的 register-write handshake
  在 receipt 完成前逾時。這只能證明該 harness 的等待風險與 pulse 邊界，
  不能當成 A pulse 已被遊戲消費，更不能當成 state transition。
- `A388` 的 `+0x54`、`A2C0` return 與 `0x08005E12` return 仍沒有一列完整、
  可重跑的 A1AC→A pulse→A2C0 receipt；下回合需先修正這個停點 handshake
  的 bounded client 行為，再重新做同一個窄觀察。

### negative

- 在已記錄的正常 KEYINPUT injection sequences 中，沒有觀察到 state 4
  handler 的共同 return、state transition 或真正 menu/event screen。
- 因為沒有正常離開 state 4，本回合沒有條件重跑
  `consumer_probe.py --trace-first-record`；因此沒有新的 eligible strict
  record、source read hit、RAM decoder、glyph writer 或 VRAM 因果鏈。
- M1.6 的 resolver 結果仍維持：live resolver hits 全在五個文字窗外，
  selected `sjis:0x146EE0` source read 是 0。不能把 A58C 的 resource pointer、
  畫面 hash 或高位 asset address 升格為文字 source。

## 4. save／runtime 邊界與下一個最小切片

只讀盤點到本作 ignored 目錄已有一個 8192-byte `.sav`，但沒有可核對來源的
mGBA save-state；本回合沒有修改、下載、偽造或依賴該 save。另以唯讀副本在
`/private/tmp` 啟動 mGBA，沒有把 save 或 ROM 納入 Git。

下一個最小切片固定為：改善共用 GDB client 在 `A1AC` live stop 後的單次
KEYINPUT destination-register write／ack receipt，重新驗證 `A1AC → edge bit 0
→ object +0x54 → A2C0 return → 0x08005E12`。只有取得 state 4 正常 return
與畫面 receipt 後，才沿既有 resolver 重跑 `--trace-first-record`；再下一步
才是 source read 後的 RAM decoder。此回合仍不可宣稱 codepage、glyph identity、
翻譯或回插成立。

# M2.9 natural state/runtime receipt（2026-08-17）

本切片只把 M2.8 static dispatcher 接到一筆 clean natural runtime receipt；不建立
翻譯 batch，也沒有寫 state、r6、descriptor、event buffer、ROM 或 save。harness
`tools/trace_m2_9_state_runtime.py` 重用 `core/gba/gdbstub_client.py`，報告只保存
寄存器、state value、計數、位址和 hash metadata。

## Ownership and bounded path

| item | receipt |
|---|---|
| ROM | clean B3EJ；SHA-256 `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0` |
| process／port | 本 session fresh mGBA PID `29182`；命令列明確指向 ignored `B3EJ_JP_candidate.gba`；`lsof` 確認 `*:2345 LISTEN` |
| GDB ownership | single connection；完成後只停止 PID `29182` |
| sequence | `none:8,start:4,none:20`；`settle=9.0s`；`max_stops=512`；input events `32/32` |
| writes | 只在 KEYINPUT read watchpoint 依 reviewed register contract 寫 active-low input register；沒有寫 game state／descriptor／event buffer |

共用 `runtime_readiness.py` 的 post-launch `ps` 子程序在本 sandbox 被拒絕，這是
tooling readiness negative；本次仍以明確 launch command、PID 與 `lsof` listener
交叉確認 ownership。這個環境限制不改變 emulator 的 GDB receipt，也不被記為遊戲
外部阻塞。

## Shared ROM identity guard adoption

本切片採用共用 `scripts/gba-rom-identity.py` 作為 ROM identity gate：以
`--expect-size 4194304 --expect-game-code B3EJ --expect-crc32 a4a1c956
--expect-sha256 d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`
執行，strict exit `0`、report `status=pass`，stored/calculated header complement
均為 `e1`；沒有使用 `--allow-invalid-header`。本作舊 `inspect_rom.py` 仍只作
bounded probe，因其 legacy checksum 公式會報 `0x13`，不把該舊結果混入共用身分
判定，也沒有修改 ROM。

## Runtime breakpoints and receipts

| edge | natural hits | metadata |
|---|---:|---|
| `0x0805D2EC` state dispatcher | `31` | state byte values `{0,3}`；observed caller LR `0x0805E081` |
| `0x0805D10C` title/menu owner | `32` | 每個 bounded input event 各一筆 owner hit |
| `0x0800C61E` normal event input | `0` | 未進入 M2.4 normal KEYINPUT reader |
| `0x0801A738` state gate | `0` | `r4+0x14` ready transition 未觀察到 |
| `0x08026054` consumer entry | `0` | 沒有 Table-B consumer hit |
| `0x080262F8` consumer index setup | `0` | natural index cohort `0` |

settled I/O 為 `DISPCNT=0x1E40`、BG0–BG3=`0x1400/0x1501/0x1602/0x1703`；最後
I/O 為 `DISPCNT=0x1F40`、BG registers unchanged。VRAM before／after SHA-256 都是
`5bbfad1b1af4a2c63e69e169077325a5210a6dc65b1d8ac2067a52fe37cf7463`，沒有把 raw
VRAM／OAM／palette dump 寫入 tracked path。

## Evidence boundary

### Confirmed

- clean B3EJ process／port ownership、single GDB connection 和 32/32 bounded input
  receipt。
- M2.8 dispatcher 在 natural path 命中 31 次；state storage 只觀察到 bounded
  values `0`、`3`，與 M2.8 的 caller `0x0805E07C`（LR `0x0805E081`）相符。
- title/menu owner `0x0805D10C` 命中 32 次，以及 known-screen 的
  `DISPCNT 0x1E40→0x1F40`／VRAM hash unchanged。

### Negative

- 此 path 沒有 normal reader、`r4+0x14` state gate、Table-B consumer 或
  `consumer_index_setup` hit；natural cohort 是 `0`。
- 因沒有 actual event byte，不能宣稱 natural index `<44`、normal runtime count、
  B/E/D formatter→glyph→VRAM receipt，也不能以 state value 推導任何 Unicode identity。

### Provisional / unknown

- `{0,3}` 是 dispatcher state storage 的 runtime observation，不是 state 3 的選單／
  戰役名稱；各 handler 與 OAM label 的 semantic mapping 仍 unknown。
- title/menu OAM known-screen receipt 仍不能代替 story E 或 battle D 的自然 consumer
  receipt；下一個安全入口是沿 `0x0805E078`／`0x0805FB00` 的 caller mode/state
  transition，或做明確標記的 E writer controlled receipt。

## Harness correction record

第一次 bounded run 在最後的 post-sequence `continue_and_interrupt` 後讀 VRAM 時遇到
mGBA stop reply 解析錯誤；fresh-process diagnostic 確認 input/state loop 已完成，故
修正 harness 收尾為停在最後 bounded stop 直接讀 I/O/hash。第二次 fresh clean run
以同一路徑成功取得上述 receipt；這是 harness transport timing correction，不是
遊戲 runtime 的永久阻塞。

## Reproduction

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m2_9_state_runtime.py \
  roms/base/B3EJ_JP_candidate.gba --port 2345 \
  --sequence 'none:8,start:4,none:20' --settle-seconds 9 \
  --event-timeout 2 --max-stops 512 \
  --output /private/tmp/b3ej-m29-state-clean.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tools/test_trace_m2_9_state_runtime.py -v
```

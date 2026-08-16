# M2.8 title/menu state dispatcher static boundary（2026-08-17）

本切片承接 M2.7 的 title-only natural negative，改做唯讀 static route；沒有啟動
mGBA、沒有修改 state／descriptor／event buffer，也沒有建立新的 translation batch。
分析器是 `tools/analyze_title_menu_state.py`，輸出只含偏移、指標、計數和 Thumb
instruction summary；完整 ROM 仍在 ignored `roms/base/`。

## Dispatcher and data boundary

| item | confirmed evidence |
|---|---|
| dispatcher | file `0x05D2EC–0x05D310`／GBA `0x0805D2EC–0x0805D310`，17 個 Thumb instructions，首尾為 `push {r4,r5,r6,r7,lr}`／`mov pc,r0` |
| state source | `0x0805D2F6` 的 PC-relative `ldr` 指向 file `0x05D310`，literal value `0x030042D1`；`ldrb` 後執行 `state - 1` |
| range gate | `cmp r0,#0x0B` + `bls 0x0805D306`；state values `1..12` 進入 table，其他值呼叫 fallback `0x0805DFA6` |
| table base | `0x0805D308` 的 literal load 指向 file `0x05D314`，literal value `0x0805D318` |
| excluded data | file `0x05D310–0x05D348` 明確排除為 state-byte literal、table-base literal 和 12 個 handler pointers；不送入 Thumb disassembler |
| transfer | `r0 = table + ((state - 1) << 2)`、`ldr r0,[r0]`、`mov pc,r0`；這個 `MOV PC` 保留當前 Thumb state |

Table B 的 44-entry count 沒有出現在這條 dispatcher；這不是 Table-B index bound。

## Pointer table and caller evidence

table file `0x05D318–0x05D348` 有 12 個 exact targets，10 個 unique handler entries：

```text
state  1  2  3  4  5  6  7  8  9 10 11 12
target  D348 D548 D744 D944 DB68 DD3C DF14 DF38 DF14 DF38 DF50 DF74
```

每個 target 都在 reviewed Thumb region `0x05D348–0x05E078`，並通過 8-byte、
4-instruction entry probe。這只證明 pointer 落點與入口解碼，不把 handler 全身
當作無 data gap 的單一 function，也不替 state 1–12 指定選單／戰役語意。

兩個 direct caller 的短 span 均通過有效 Thumb 解碼：

- `0x0805E07C → 0x0805D2EC`；caller 接續呼叫 `0x0805CBA0`、`0x08038AD8`。
- `0x0805FB06 → 0x0805D2EC`；callsite 前後的 bounded span 沒有把 literal island
  當成 code。

另確認 title/menu display owner `0x0805D10C`：`0x0805CA94` direct-call 它，
owner span `0x0805D10C–0x0805D27C` 的 182 個 Thumb instructions 首尾完整解碼，
並在 `0x0805D110` 呼叫 title KEYINPUT poll `0x0805CF58`。這是 title/menu input／
display edge，不是 Table-B consumer。

## State lifecycle receipt

state 12 的 entry `0x0805DF74` 有一段獨立可審核 tail：`0x0805DF80` 的 literal
load 指向 `0x0805DF90`，value 同為 `0x030042D1`；`0x0805DF84` 將 zero 寫回
state byte，接著 branch 到 `0x0805DFA6`。這證明同一 state storage 的 reset edge，
不證明該 state 的畫面名稱或與 normal event descriptor 的語意等價。

## Evidence classification

### Confirmed

- dispatcher code span、range/fallback branch、literal pool 與 data gap。
- 12-entry pointer-table boundary、10 unique handler targets、12 個 entry probes。
- `0x0805E07C`／`0x0805FB06` direct callers，以及 `0x0805CA94 → 0x0805D10C`
  title/menu owner edge。
- state 12 reset tail 對 `0x030042D1` 的 write。

### Provisional

- 依 M2.6／M2.7 的 OAM known-screen receipt，這組 state handlers 很可能是 title／
  menu-side render state；目前只保留這個 family-level label。
- 各 handler 的實際 menu row、battle mode 或 OAM label 對應尚未由 pointer／runtime
  收據逐項證明。

### Negative / unknown

- 這條 chain 沒有 Table-B `0x08026054` call、沒有 `r6+0x02` bound，也沒有自然
  event byte actual index；自然 cohort 仍為 0，`<44` 仍未證明。
- `r4+0x14` 何時由 zero 變為 normal event-ready、以及 story E／battle D 的自然
  caller 仍未知。

## Reproduction

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_title_menu_state.py \
  roms/base/B3EJ_JP_candidate.gba \
  --output /private/tmp/b3ej-m28-title-menu-state.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tools/test_analyze_title_menu_state.py -v
```

下一個安全缺口是沿 `0x0805E078`／`0x0805FB00` 的 caller function 和 M2.4 的
`0x0801A738` state gate 做 bounded cross，或取得明確標記的 E story writer
controlled receipt；兩者都不能冒充自然 `<44` 或自然劇情畫面 QA。


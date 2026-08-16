# M2 natural renderer／loader consumer boundary（2026-08-16）

## 範圍

本回合只重跑已審核的固定 runtime entries，沒有新增 pointer scan、沒有修改
state/object/save/ROM，也沒有輸出 source、glyph、RAM 或 VRAM bytes。三個工具都
沿用 `core/gba/gdbstub_client.py`；B3TJ identity 每次 invocation 都通過
`TOWNARIKIRI3`／`B3TJ`／`AF`／16 MiB／CRC32 `1867CCEF`。

## natural-flow receipts

### `0x08001414` font-map candidate

使用 [`tools/font_consumer_probe.py`](../tools/font_consumer_probe.py)，固定只觀察
`0x08001414`、由 `r2` 推導的單一 `0x080DDCC4 + r2*0x20` slot、transform 與
`0x03000560` scratch。sequence 是 `start:8,none:12,a:8,none:12`，共 40 events：

| 項目 | 結果 |
| --- | --- |
| termination | `sequence-exhausted-without-font-hit` |
| font-map entry hits | `0` |
| asset read hits | `0` |
| transform/scratch pipeline stops | `0` |
| strict source edge | `unconfirmed-by-design` |

這是自然流程未到達既有 font-map candidate 的 bounded negative，不是否定 static
asset arithmetic，也不表示 codepage 或 glyph identity 已知。

### `0x080014F4` format-loop candidate

使用 [`tools/format_record_runtime_probe.py`](../tools/format_record_runtime_probe.py)
與同一 40-event sequence，要求 `--trace-first-strict`。第一次 fresh process 在
GDB setup 得到 `OSError errno 49`（`Can't assign requested address`），沒有任何
game stop；依既有 mGBA listener race policy 停止該自有 process 後 fresh retry。

fresh retry 的結果：

| 項目 | 結果 |
| --- | --- |
| termination | `sequence-exhausted-without-strict-record-format-hit` |
| key events | `40` |
| format entry hits | `0` |
| strict source read hits | `0` |
| lookup/asset/scratch pipeline | `0` |

因此 setup-only failure 沒有被混入遊戲 negative；retry 才是本回合的 natural-flow
formatter result。既有 `8,938` strict records 仍只是 static source candidates。

### `0x080021A8` loader／builder boundary

使用 [`tools/font_record_runtime_probe.py`](../tools/font_record_runtime_probe.py)，
sequence 為 `start:1,none:300,a:1,none:300`，`602` events，並開啟
`--trace-builder-input`。同時以 `--inject-record-offset 0x146EE0` 請求只允許
exact strict record start 的 argument injection：

| 項目 | 結果 |
| --- | --- |
| termination | `sequence-exhausted-without-loader-hit` |
| loader entry hits | `0` |
| builder `0x08015B74` hits | `0` |
| source/asset read hits | `0`／`0` |
| key events | `602` |
| strict record requested | `sjis:0x146EE0`／`0x08146EE0` |

因 loader entry 根本沒有 hit，工具沒有執行 `r1` register injection；receipt 的
`strict_record_source_read` 仍標為 `injected-source-pipeline-only`，這只是請求的
分類，不是 pipeline proof。此結果同時保留 **natural-flow**（loader/builder 未命中）
與 **argument-injected**（未執行）的界線，不把高位 asset address 或 static table
當作文字 consumer。

## 分類與下一步

| 證據 | 分類 |
| --- | --- |
| state 4→7、state7→A82AC、A82AC `r0+0x28=0` | confirmed natural-flow readiness edge |
| font-map／format-loop／font-loader entry in these bounded sequences | negative: no natural hit |
| `0x08146EE0` requested injection | requested strict input, not executed |
| decoder、code-unit→glyph、glyph identity、VRAM writer | unknown |
| 翻譯、容量、回插、BPS、runtime text QA | not started／not proven |

目前不能宣稱 state7 沒有文字，也不能宣稱五窗 extractor 錯誤；這些 receipts 只
說明所選 bounded startup/state7 sequence 沒有到達三個已知候選 entry。既有
`state7_readiness_probe.py` 已經取得 A82AC 的 natural-flow readiness boundary，
因此下一個最小 runtime slice 應改為同一正常 state7 session 的兩個固定 callsite
`0x08001652`／`0x08001D92`，再接 parser `0x080025CC` 與 selected strict
read-watch；不增加 pointer scan，也不以 argument injection 取代正常流程。這個
slice 目前受 mGBA listener setup blocker 限制，不能把 static call chain 升格為
live consumer。

## QA receipt

- 本作 tests：`83` passed。
- `scripts/check-repository-safety.rb`：passed（本次檢查看到 1,012 個 visible files）。
- `git diff --check -- games/tales-of-the-world-narikiri-dungeon-3`：passed。
- `core/gba` tests：`20` 執行，其中 2 個 `runtime_validation` static fixture tests
  failed；失敗來自共享工作區其他 session 對
  `core/gba/runtime_validation/{manifest.py,static_checks.py}` 與其 test 的未提交
  修改。本作沒有 stage 或修改這些 core paths，故不把 core suite 報成通過。

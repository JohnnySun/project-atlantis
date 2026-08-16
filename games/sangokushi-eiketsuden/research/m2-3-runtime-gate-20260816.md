# M2.3 Table B runtime gate

日期：2026-08-16（Asia/Taipei）。本切片只處理日版 B3EJ 的 Table B，不建立《孔明傳》資料、翻譯 batch、ROM、完整日文、raw dump 或圖片。runtime 報告只留在 ignored `work/runtime/`；本文件只保存位址、計數、狀態、寄存器 provenance 與 hash。

## 結論分層

| 層級 | 結論 |
|---|---|
| confirmed-static | `0x080264A4` initializer 在 `0x08026510` 呼叫 `0x0801929C` event builder；builder 回傳值經 `u16` 正規化後寫入 `r6+0x02`，同一 caller 把 `sp` output buffer 寫入 `r6+0x1C`。 |
| confirmed-static | builder empty path 的 `cmp r5,#0x2B`／`bls` 產生 index `0..43`、回傳 count `44`；normal path 讀 runtime table `[0x02014E78]`，以 `0xFF` 終止，count 沒有可由 ROM 靜態推出的全域 `<44` 證明。 |
| confirmed-runtime / controlled | 受控 RAM fixture 的 dispatch case `20` 進入 `0x08026054`，實際 `event_byte=0x00`、masked index `0`、event-array index `0`、local length `1`、caller LR `0x0800C735`；這是 controlled cohort 的一筆 `<44`，不是自然 reachability 或全域安全證明。 |
| confirmed-runtime / controlled | controlled B[0] `0x08078528` 經 `record_wrapper 0x0800D8F0`、formatter `0x0800D3FC`、writer `0x0800CAD8`、SJIS renderer／codepage lookup／glyph expand，取得 3 組 cache→VRAM→tilemap receipts。 |
| confirmed-runtime / controlled | `0x9594` 的 runtime codepage index `1301` 與 Unicode identity `U+90E8`，cache `0x02000000` 128-byte hash 與 VRAM `0x0600C080` after hash 相同；tilemap writer 也在 `0x02013050` 有 before/after hash 變化。glyph addressing 與 Unicode identity 分開記錄。 |
| negative / bounded | 32-event natural navigation cohort 沒有 consumer／index setup hit，`natural_reachability=not-observed`、natural index cohort 為 0。這是否代表選單路徑尚未正確導航，不能外推成遊戲永不觸發。 |
| negative / tooling-only | headless build 的實際 GDB port 是 `2346`（`0x92A`，被其他 session 使用）；另一個現成 build 的 `23901` 也由其他 session 使用。24567 shim 沒有攔到該 binary；24569 forward readiness 成功但 GDB connection closed。這些是 transport 結果，不是遊戲 gate 結論。 |
| unknown / pending | 自然 event index `<44`、normal-path runtime table 的所有值、未命中的 U+306B／U+529B runtime glyph identity、完整輸入導航與 ROM encoder／relocation／字庫回插邊界仍未證實。 |

## Static upstream chain

`tools/m2_3_static.py` 只解碼安全的 Thumb spans，並明確排除 inline data gaps：

| 區段 | 結果 |
|---|---|
| initializer | file `0x0264A4–0x026646`（GBA `0x080264A4–0x08026646`）；data gaps `0x026546–0x026554`、`0x0265A0–0x0265B4`、`0x026626–0x026630` 不當作程式。 |
| builder call | `0x08026510 BL 0x0801929C`；args 是 `r0=input structure`、`r1=sp output buffer`、`r2=1`。 |
| r6 fields | `strh r2,[r6,#2]` at `0x0802658E`；`str r0,[r6,#0x1C]` after `mov r0,sp` at `0x08026596–0x08026598`。 |
| builder | file `0x01929C–0x019382`（GBA `0x0801929C–0x08019382`）；literal `0x080192FC` 值為 runtime table pointer `0x02014E78`。 |
| empty path | `0x080192F6 cmp r5,#0x2B`、`0x080192F8 bls 0x080192EC`，最後 index 為 43、return count 為 44。 |
| normal path | `0x0801936C cmp r0,#0xFF`；count 在 `0x08019374 adds r0,r5` 完成，runtime 觀測點是下一個指令 `0x08019376`。 |
| consumer | `index = u16(r6+6)*u16(r6+8)+u16(r6+0)+u16(r6+4)`，只與 `u16(r6+2)` 比較；event byte 再做 `& 0x7F`。沒有靜態 `<44` compare。 |

因此靜態 chain 已證實「builder count／buffer → r6 → consumer event byte」，但只對 empty path 有 44 的硬證據；normal path 必須依 runtime 值或 bounded cohort 判定。

## Controlled runtime receipt

執行使用官方 mGBA 自己的 process、自己的 GDB client、KEYINPUT watchpoint 與 `M23_BREAKPOINTS`；ROM／save 沒有寫入。controlled fixture 只寫 disposable EWRAM：

| 欄位 | 值 |
|---|---|
| provenance | `controlled-consumer-call-hijack`；natural reachability 不宣稱 |
| consumer entry／dispatch | `0x08026054`／case `20` |
| r6 base／event array | `0x0203F000`／`0x0203F100` |
| event byte／masked index | `0x00`／`0` |
| local bound／formula result | `u16(r6+0x02)=1`；formula result `0` |
| observed event array index | `0`；`0 < 44`；caller LR `0x0800C735` |
| B[0] record pointer | `0x08078528`，wrapper event `record_pointer_is_B0=true` |
| formatter／writer | source pointer `0x08078528` → formatter `0x0800D3FC` → output writer `0x0800CAD8`；formatted buffer observed at `0x03007C7C` |

同一個最多 32 controlled-event slice 產生 9 個 receipts：3 glyph-cache、3 `glyph-cache-to-vram`、3 tilemap-writes。三組 glyph addressing 摘要如下；hash 是資料一致性 receipt，不是 raw glyph dump：

| code unit | codepage index / Unicode identity | cache 128-byte SHA-256 | VRAM destination / after SHA-256 | tilemap after SHA-256 |
|---|---|---|---|---|
| `0x8250` | `30` / `unmapped` | `4432b759e40b3eff23fdaec22e52a07079c97c9e5b5be1cbfdcd999369f11447` | `0x0600C000` / `4432b759e40b3eff23fdaec22e52a07079c97c9e5b5be1cbfdcd999369f11447` | `3a383faca693795ac6ec371d785d92c700469dd5eb2b86790bd77b67988efeff` |
| `0x9594` | `1301` / `U+90E8` | `e56e457e233682a20ff319087d8d924d9e20da83830db08bdb75960ce27ca9f3` | `0x0600C080` / `e56e457e233682a20ff319087d8d924d9e20da83830db08bdb75960ce27ca9f3` | `e45cd10759bf1183fd9276e7adc478b02e41a5b01e3eef0dfea83dc026b6c542` |
| `0x91E0` | `1034` / `unmapped` | `fadd12f565bcbd471cd8dfbdce477c5f559151b99854cde135a086b04d20e7c2` | `0x0600C100` / `fadd12f565bcbd471cd8dfbdce477c5f559151b99854cde135a086b04d20e7c2` | `7e0e0f984ae4f8e29a595210c48a34b351804498b8c3f732af5aae21c05ef35a` |

The first two rows are sufficient for the reviewed U+90E8 cross-check; no Unicode identity is inferred for `0x8250` or `0x91E0`. The helper receives `r2=0x80` as a byte count. The 32-byte copy helper at `0x08000214` subtracts `0x20` per transfer, so each receipt length is 128 bytes, not 4096 bytes.

## Gate and translation boundary

The runtime gate is **partially closed for the controlled experiment only**:

- controlled actual-index evidence: one row, `0 < 44`;
- natural actual-index evidence: zero rows;
- controlled formatter→glyph cache→VRAM/tilemap edge: confirmed for the three observed code units, with U+90E8 identity cross-checked;
- natural Table-B reachability and global event-index safety: still pending.

The minimal future translation gate is design-only: retain each record's source hash and payload length, require NUL／opaque-control／format invariants, encode strict Shift-JIS, resolve every new code unit through the reviewed codepage table, and reject glyphs without a verified font slot. Existing 44-record decode→encode no-op verification remains record-level only. No translation batch or ROM insertion is started by M2.3.

## Reproduction

Static report:

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/m2_3_static.py \
  roms/base/B3EJ_JP_candidate.gba --output /private/tmp/b3ej-m23-static.json
```

Runtime report (requires a caller-owned mGBA/GDB session):

```text
PYTHONDONTWRITEBYTECODE=1 python3 tools/trace_m2_runtime.py \
  roms/base/B3EJ_JP_candidate.gba --port 2345 --pipeline \
  --controlled-consumer --natural-events 32 --controlled-events 32 \
  --output work/runtime/m23-pipeline-controlled-consumer.json
```

The ignored report retains hashes and runtime metadata only; it does not enter Git.

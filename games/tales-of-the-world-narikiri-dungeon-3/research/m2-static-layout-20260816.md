# M2 固定 layout／width-table bounded 證據（2026-08-16）

## 範圍

這一回合只驗證既有反組譯已指出的固定位置，不做新的全 ROM pointer scan，
也不把圖形資源路徑冒充文字 consumer。`tools/static_layout_probe.py` 不依賴
Capstone，僅對 B3TJ identity、ROM `0x1BE31C–0x1BE3A0`、五個既知 literal
reference 與 `0x080C90F8` 的 19-entry dispatch table 做一致性檢查。

## 證據

- `0x080C8F7C`、`0x080C8FF0`、`0x080C9074`、`0x080C92D0`、`0x080C92E0`
  的 bounded literal pool 均指向 GBA `0x081BE31C`；這是固定 ROM data reference，
  不是 runtime read watchpoint。
- `0x081BE31C–0x081BE3A0` 是 132 bytes／66 pairs 的小表，位在 strict text-pool
  範圍內一個較晚的資料區段。相鄰資料呈現可解碼候選與 `%` token，但本 probe
  只保存該表的 SHA-256、pair count、zero/non-zero 與 value histogram，不保存 raw。
- `0x080C90F8` 先將輸入限制為 `0..0x12`，再從 `0x080C9118` 取 19 個 bounded
  targets；此 dispatch 與 `0x080C9058` 的數值 code／width helper 關聯，仍只
  能說是 layout/resource path。

## 狀態界線

### Confirmed static

- B3TJ ROM identity、固定 literal location、width-table window size／hash 與
  dispatch count 可 deterministic 重算。

### Provisional

- 該小表很可能是 ASCII／UI layout width metadata：helper 會以 `code - 0x23`
  做 pair lookup，且 caller 傳入 `0x23` 起的有限 code values。這是靜態 calling
  pattern，不是標準 Shift-JIS glyph identity。

### Negative / unknown

- 尚無 state 7 runtime source read、RAM decoder 或 VRAM causal chain 可把此表
  連到五窗內某個 strict record。
- 尚未確認這 66 pairs 是文字寬度、資源 descriptor 或其他 UI metadata；不可用它
  建立日文→zh-TW codepage、字型替換或回插 builder。

## 重跑

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/static_layout_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --out games/tales-of-the-world-narikiri-dungeon-3/research/m2-static-layout-metadata.json
```

ROM、raw bytes、畫面與完整原文仍留在本機 ignored／`/private/tmp`。

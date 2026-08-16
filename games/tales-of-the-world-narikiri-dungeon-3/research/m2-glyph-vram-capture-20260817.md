# M2 bounded glyph destination／VRAM capture receipt（2026-08-17）

本回合把上一份 argument-injected source→glyph edge 延伸到實際的 transform
destination 與一次完整 VRAM snapshot。它仍不是自然 menu/event provenance，也不
宣稱已知 glyph identity、完整 codepage、控制碼、字寬或可逆回插。

## Session boundary

- ROM：B3TJ，16 MiB，CRC32 `1867CCEF`，SHA-256
  `d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394`。
- mGBA：fresh own PID `38379`，固定編譯 GDB port `39123`，`127.0.0.1`，單一
  client connection；完成後只停止該 PID。
- navigation：沿既有 `navigation_harness.lua` state4→state7 sequence；與前一回合
  相同，是 argument-injected harness evidence，不是自然流程 save/state override。
- selected record：`sjis:0x140D68`，GBA `0x08140D68`，source span hash
  `2dc05858bd37ff9a2e829aafded4f7ab9bfa6c5ff37eb9a66dbcb3f627ac8ac5`。
- probe bound：`--max-stops 128`，實際 25 stops；所有輸出只含 address、register、
  count、hash、status。ROM、source bytes、RAM/VRAM raw dump 均留在本機 ignored／
  `/private/tmp`。

本回合 QA 也開始採用共用 guard：

- `scripts/gba-rom-identity.py`：exit `0`／`status=pass`，header complement、size、
  game code、CRC32、SHA-256 五項均 pass。
- `scripts/gba-runtime-session.py preflight --port 39123`：普通 sandbox 嘗試為
  exit `2`／`unknown`／`PermissionError`；同一命令在已授權 localhost socket 下為
  exit `0`／`pass`／port free。這只證明 preflight，不代表 runtime QA pass。

本作 breakpoint、watchpoint、state/navigation、pointer 與 glyph 位址仍由本作
adapter 管理；下一個 runtime gate 將使用同一共用 preflight，再由本作 probe 執行
transfer-specific actions。

本回合採用的共用 guard 命令與結果如下（輸出均在 `/private/tmp`）：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/gba-rom-identity.py \
  /Users/bmy001/Work/project-atlantis/games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --expect-size 16777216 --expect-game-code B3TJ --expect-crc32 1867CCEF \
  --expect-sha256 d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394 \
  --output /private/tmp/b3tj-identity-common-20260817.json
# exit 0 / status pass

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/gba-runtime-session.py preflight \
  --port 39123 \
  --session-report /private/tmp/b3tj-preflight-common-20260817-escalated.json
# ordinary sandbox: exit 2 / unknown / PermissionError
# authorized localhost-socket retry: exit 0 / pass / free
```

這一回合的 probe 改用兩個窄 runtime hooks：

1. 對上一回合已 live-confirmed 的 IWRAM destination `0x030007A0` 設 4-byte
   write watchpoint，要求 watch hit 時 `r1` 精確等於該位址。
2. 對 transform continuation `0x08001458` 設單一 breakpoint；命中後先單步到
   `0x0800145A`，才讀取 IWRAM／VRAM。沒有再安裝四個 recurring store breakpoint，
   避免 transform loop 被自身 software breakpoint 卡住。

## Confirmed runtime evidence

本回合在同一條 connection 重新取得上一回合的前置 edge：

| edge | receipt |
|---|---|
| strict source read | `0x080027F4`，LR `0x08001651`，`r1=0x08140D68` |
| parser output write | `0x080027EE` → RAM `0x03001468` |
| formatted-buffer read | `0x08001504`，source buffer `0x03001468` |
| glyph asset read | `0x080011D6`，asset `0x081670C4`，LR `0x08001459` |
| destination write watch | writer PC `0x080011F8`，watch `0x030007A0`，`r1` exact match |
| transform continuation | breakpoint `0x08001458`，single-step PC `0x0800145A` |

destination `0x030007A0` 的 32-byte sample 只保存 hash
`2995cde83880681e9bac9f023b689a45abdd135876ba39eb69671e0d9aa9512a`，非零 byte
數為 32。這是 runtime RAM destination／write evidence，不是 source bytes 或 glyph
identity。

## ROM→VRAM exact-match result

在 transform-return single-step 後，成功讀取完整 `0x18000` bytes 的 VRAM metadata：

- address `0x06000000`、length `98304`
- SHA-256 `73ee17fe8ae2b5fb6d1eeb9de9e798ac8031f23f037698d51deacb7f179aec72`
- nonzero bytes `62716`
- destination 32-byte sequence 的 exact-match offsets：空集合

因此本回合的嚴格結論是：**在 transform-return snapshot 中沒有觀察到
`0x030007A0` 這個 32-byte transformed tile 的 ROM／RAM sample → VRAM exact byte
match**。這是 confirmed negative for this capture point，不是「VRAM 沒有文字」或
「資產已壓縮」的結論；它只把下一個問題縮小到 transform 後的搬運／tilemap／DMA
時序，或該 32-byte sample 並非直接 VRAM tile representation。

第二次 post-capture VRAM read 被 return breakpoint 的再次命中干擾：一次 bounded
response-class diagnostic 看到 `S02` 後 `S05k`，故 report 將 post sample 標為
`unavailable`，沒有用它推論 hash change。第一個完整 transform-return VRAM
snapshot 仍保留為 authoritative evidence。

## Evidence boundary

### Confirmed

- argument-injected strict record→parser output→formatter→glyph asset→IWRAM
  destination write→transform continuation。
- stopped transform-return 時完整 VRAM metadata 可讀，且 exact-match search 是
  deterministic、bounded、只輸出 offsets；本次結果為空集合。

### Provisional／unknown

- `0x030007A0` 後續是否由 `0x08001DBC`、DMA、tilemap writer 或另一個 blitter
  搬到 VRAM：unknown；既有 `0x08001DBC` 仍只是 static writer candidate。
- `0x081670C4` slot 的 glyph identity、4bpp layout、字寬與 codepage：unknown。
- post-run VRAM hash change：unknown，因第二次 read 被 breakpoint re-entry
  干擾；不以不可重現的 partial read 補推。
- natural-flow pointer provenance、selected `sjis:0x146EE0` natural hit、控制碼
  語義、變長容量與回插：仍未證明。

### Next minimum slice

沿同一 argument-injected edge，在不擴大 resolver／pointer scan 的前提下，找一個
能避開 return breakpoint re-entry 的 post-transform transfer observation：優先以
已知 IWRAM destination 的單一 write／DMA／VRAM watch 或 safe later PC 取得第二個
bounded VRAM sample，再做 tilemap／DMA destination metadata 與 exact-match 交叉
驗證。下一個 runtime gate 將採用共用 `scripts/gba-rom-identity.py` 及
`scripts/gba-runtime-session.py preflight`；固定 port build 以實際 compiled
`39123` 記錄，ownership pass 不升格成 runtime pass。

可重跑本回合 probe（ROM path 與 mGBA executable 應改成絕對路徑，並先確認
`39123` 只屬於本 session）：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/live_consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port 39123 --max-stops 128 --capture-glyph --post-capture-seconds 0.25 \
  --output /private/tmp/b3tj-glyph-capture-final.json
```

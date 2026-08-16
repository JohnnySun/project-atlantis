# M2 bounded live parser／glyph consumer receipt（2026-08-16）

本回合完成一條可重跑、但明確標為 **argument-injected** 的 B3TJ runtime edge。
它補足了 M1.5／M1.8 的「自然流程尚未讀到 exact strict record」缺口；不把
register injection 改寫成自然 menu/event pointer provenance，也不宣稱完整
codepage、glyph identity、VRAM sink 或可逆回插已成立。

## 可重跑邊界

新增：

- `tools/navigation_harness.lua`：在 frame 1 後安裝本作已審核的 state4、A1AC、state7
  與 KEYINPUT post-load hooks。它只把 active-low START／A／release 寫入 KEYINPUT
  load 的 `r1`，不寫 state、object、save 或 ROM。
- `tools/live_consumer_probe.py`：使用共用 `core/gba/gdbstub_client.py`，只跑一條
  GDB connection；觀察前兩次 parser entry，第二次才對 exact strict record 做一次
  `P1`，要求 `OK` 後才安裝 source／output／glyph watches 與固定 glyph store
  breakpoints。報告只輸出 metadata、register、address、hash、count。
- `tests/test_live_consumer_probe.py`：驗證 strict boundary、RAM／非文字指標拒絕、
  固定 Thumb store 位址與 metadata-only report。

本回合使用 fresh own mGBA／`127.0.0.1:39123`／單一 client。navigation receipt 為
state4 gate frame 692、START `0x03F7`、A1AC frame 694、A `0x03FE`、8 次 release，
state7 frame 786，state bytes `next/current/previous = 07/07/04`。這些輸入是
**argument-injected harness evidence**；沒有直接覆寫 state、object 或 save。

## Confirmed runtime edge

第二次 parser entry 的自然前置狀態為：第一次 `r1=0x0200C798`（RAM），第二次
`r1=0x081489EC`。後者雖位於 `text-pool`，卻是
`strict-window-nonstrict-offset`；其相鄰 NUL span 僅 3 bytes，hash 為
`5c9a38920a8ec22dc2be07e62a21d22cbb71676cc5326e349f8e38f98f9c18d9`。因此它不被
當成可翻譯的 strict source record。

接著只做一次 `r1=0x08140D68`，GDB response 為 `OK`。該位置是 strict
`sjis:0x140D68`，raw length 28、allocated span 29，source span hash 為
`2dc05858bd37ff9a2e829aafded4f7ab9bfa6c5ff37eb9a66dbcb3f627ac8ac5`。在同一條
connection、bounded 24 stops 內取得：

| 邊 | runtime 證據 |
|---|---|
| source read | `0x080027F4`，LR `0x08001651`，r1=`0x08140D68` |
| parser output | RAM `0x03001468`，writer `0x080027EE` |
| formatter | callsite `0x08001652` → entry `0x080014F4` |
| formatted buffer read | `0x08001504`，仍從 `0x03001468` 消費 |
| glyph lookup candidate | `0x08001414`，codepoint index `0x44A0` |
| glyph asset read | `0x081670C4`，reader `0x080011D6`，LR `0x08001459` |
| fixed transform store | `0x080011F6`，`str r4,[r1]`，destination `0x030007A0` |

因此目前可確認：

```text
strict source (argument-injected)
  -> 0x080025CC parser / 0x03001468
  -> 0x080014F4 formatter
  -> 0x08001414 glyph candidate
  -> 0x081670C4 asset read
  -> 0x080011F6 fixed transform store -> IWRAM 0x030007A0
```

`0x08004D90` codepoint lookup 與 `0x08001DBC` writer candidate 在本次 bounded
strict run 未命中；它們仍只保留既有 static／provisional 分類。原始 JSON report
留在 `/private/tmp`，提交的摘要見
[`m2-live-consumer-glyph-metadata.json`](m2-live-consumer-glyph-metadata.json)。

## Boundary and next slice

### Confirmed

- exact strict record source read 及其 caller／destination buffer。
- parser output、formatter entry、formatted-buffer read。
- 一個實際 code-unit 產生的 glyph asset read，以及固定 transform store 的 IWRAM
  destination。

### Provisional／unknown

- argument-injected edge 尚不能證明自然 pointer table、事件、角色／服裝／技能、
  戰鬥或選單資料會自然傳入同一筆 record。
- formatter 的 SJIS-like arithmetic、`0x44A0` index、`0x20` asset stride 仍不足以
  證明完整 codepage、控制碼語義、字寬表或 glyph identity。
- `0x030007A0` 是 transform destination candidate，不是 VRAM；IWRAM→tilemap／
  VRAM 的因果鏈與 ROM→VRAM exact glyph match 尚待下一個 bounded slice。
- `sjis:0x146EE0` 的 natural source read 仍是 negative，沒有被本回合替換成
  selected record 的自然命中。

下一個最小切片是固定這個已確認的 glyph transform destination，於同一個文字 edge
上做 RAM／VRAM metadata capture 與 exact-match 交叉驗證；不是擴大 pointer scan，
也不是開始翻譯。

# M2.7 menu-selection bounded negative（2026-08-16）

M2.6 已證明 GDB input injection 可讓 clean B3EJ 從 title baseline 進入 OAM menu
state。本切片只再試一條明確的 menu-selection path，確認是否能自然抵達 M2.4
static chain 的 normal event reader；沒有修改 runtime state、descriptor、r6 或 event
buffer，也沒有建立 controlled consumer call。

## Path and ownership

```text
fresh clean B3EJ process, port 2345, single GDB connection
settle=9.0s
none:8,start:1,none:12,down:4,none:2,a:2,none:3
natural_events=32, event_timeout=2s
```

PID `3751` 的命令列精確指向 ignored clean B3EJ ROM，readiness 為 `true`。輸入
仍只在 KEYINPUT read stop 改寫 register；32/32 stops 都在 title poll
`0x0805CF5E`，所以 register-specific helper 全部寫 `r0`。沒有命中 normal reader
`0x0800C61C` 的 `ldrh r1,[KEYINPUT]`，也沒有命中 state loop 的 builder／consumer
／formatter／glyph breakpoints。

## Receipts

| item | result |
|---|---|
| settled display | `DISPCNT=0x1E40`; BG0–BG3=`0x1400/0x1501/0x1602/0x1703` |
| final display | `DISPCNT=0x1F40`; BG registers unchanged |
| natural builder／consumer／formatter／glyph | all `0` |
| natural index cohort | `0`; normal runtime count not observed; `<44` not proven |
| VRAM before／after | `5bbfad1b1af4a2c63e69e169077325a5210a6dc65b1d8ac2067a52fe37cf7463` / same |
| final OAM | same 24-sprite menu layout as M2.6; raw dump and image ignored |

## Boundary

- **confirmed**：這條 DOWN／A sequence 沒有跨到 reviewed normal event reader；title→
  OAM menu state receipt仍可重現。
- **negative**：延長或改變同一 title poll sequence 沒有提供自然 Table B index、D
  event consumer、E story consumer 或 glyph writer receipt；不把它當全遊戲不可達證明。
- **unknown**：menu selection 的實際 state owner／input consumer、OAM label asset 的
  source pool，以及 normal path `r4+0x14` 何時變為 nonzero。

下一個安全入口是 static 追 `0x0805D10C` caller／title menu state owner 與
`0x0801A738` state gate 的對應；不再重複 title-only runtime path，並維持目前
story-event E／battle B-D 的 static／round-trip 證據分層。


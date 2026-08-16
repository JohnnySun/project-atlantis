# M2.6 title→menu known-screen runtime slice（2026-08-16）

本切片只驗證一條可重現的 title→menu 畫面路徑，並把「畫面已跨 state」和
「已定位文字 pool 的 consumer 已命中」分開。mGBA 使用本 session 自有 fresh
process、port `2345`、每個 process 一條 GDB connection；clean ROM 與 event-system
batch 2 的 BPS output 各跑一次。ROM、sav、raw VRAM／palette／OAM dump、PPM／PNG
均留在 `/private/tmp`，沒有進 Git。

## Navigation contract

兩次使用相同 bounded sequence：

```text
settle=9.0s
none:8,start:4,none:8,a:4,none:8
natural_events=32
event_timeout=2s
```

輸入只在 reviewed KEYINPUT read watchpoint 改寫 CPU register，沒有寫 ROM、r6、
event buffer、descriptor 或 consumer PC；因此這是
`natural-navigation-with-GDB-input-injection`，不是 controlled consumer fixture。
本次 title path 的 watchpoint stop 均位於 `0x0805CF5E`，寫入 `r0`。normal event
poll 若命中 `0x0800C61E–0x0800C622`，新 harness 會改寫 `r1`，因為該 reader 的
`ldrh r1,[KEYINPUT]` 與 title reader 的 register contract 不同；本 cohort 沒有
命中 normal reader。

GameFAQs 的 GBA 操作整理把 START→main menu 作為導航假設；此來源只校準路徑與
畫面類別，不作 B3EJ 原文或翻譯來源：
[GameFAQs GBA guide](https://gamefaqs.gamespot.com/gba/925912-san-goku-shi-eiketsuden/faqs/38912)。

## Runtime receipts

| run | ROM | ownership／port | settled I/O | final I/O | natural pipeline |
|---|---|---|---|---|---|
| clean | B3EJ clean SHA-256 `d61e284b…f0c97b0` | fresh PID `95146`, port `2345`, readiness `true` | `DISPCNT=0x1E40`; BG0–BG3=`0x1400/0x1501/0x1602/0x1703` | `DISPCNT=0x1F40`; BG registers unchanged | builder／consumer／formatter／writer／codepage／glyph／VRAM copy／tilemap all `0` |
| event-system batch 2 | patched SHA-256 `8332f030…34d4a3dc`；source CRC `a4a1c956`、target CRC `e3c08899` | fresh PID `98087`, port `2345`, readiness `true` | same clean baseline | same `DISPCNT=0x1F40` and BG registers | same all-zero pipeline；natural Table B cohort `0` |

兩次 run 的 VRAM before／after hash 都是
`5bbfad1b1af4a2c63e69e169077325a5210a6dc65b1d8ac2067a52fe37cf7463`，表示這個
state transition 主要切換 display／OBJ configuration，而不是由本次 reviewed
text writer 產生新的 VRAM bytes。

## Known-screen renderer evidence

以共用 `core/gba/render_oam.py --mapping 1d` 讀取每次 run 的 ignored OAM／palette／
VRAM，兩次均輸出 `240x160`、`24` 個 visible sprites。人工檢視的 OAM composite
顯示三列主選單按鈕，語意可辨識為記錄刪除、武將列傳、自由模式；這是畫面類別／
版面證據，不是把 OAM tile address 當成 Unicode identity，也沒有把完整日文按鈕
文字寫入 tracked research。

clean 與 patched run 的 renderer receipts：

| artifact | clean／patched hash | 結論 |
|---|---|---|
| final VRAM | `5bbfad1b…cf7463`／`5bbfad1b…cf7463` | identical |
| final OAM | `1b50ba640d4576a4fc46db4230926ee2bb6dff1f33192651320b4f6a74f50a6f`／同值 | identical |
| OAM composite PPM | `8dd7d91c206f080c3307edbe0435a64fae7433eee6a8134ab955acfb19869a47`／同值 | identical |
| visible sprite count | `24`／`24` | identical |

## Confirmed / provisional / negative / unknown

- **confirmed**：fresh B3EJ process ownership、single-connection runtime、title I/O
  baseline、GDB input receipt、`DISPCNT` 的 title→menu state change，以及共用 OAM
  renderer 的三列 menu layout／24 visible sprites。
- **confirmed-static**：event-system batch 2 的 D pointer／record fixed-slot、custom
  glyph、re-extract 和 BPS apply gate；patched ROM identity／CRC 也符合既有 receipt。
- **provisional**：公開 START→main-menu 流程與 OAM menu category 相符；OAM 顯示的
  menu labels 尚未和 D `0x0D4D00` 的某個 record 建立 pointer／consumer 對應。
- **negative**：兩次 32-event path 均沒有 builder、Table B consumer、record
  wrapper、formatter、common codepage、glyph cache、VRAM copy 或 tilemap hit；
  event-system batch 2 patched menu 與 clean menu 的 OAM／VRAM／render hash 完全
  相同，不能宣稱已完成翻譯 menu QA 或 D natural consumer proof。
- **unknown**：三列 OAM menu 的實際 ROM asset／pointer pool、自然 event index
  `<44`、E natural formatter→glyph receipt、以及 menu label 的 Unicode identity。

macOS Accessibility 不允許本次 `osascript` 實際 GUI key event；因此 GDB register
input 仍是唯一可重現的輸入路徑，不能把這筆 receipt 說成硬體／GUI 輸入證據。


# A9PJ 2A text record／code-unit／control candidate slice（2026-08-16）

本切片把已由 M1.6／M1.7 runtime 與 ROM 控制流支持的 record arithmetic 整理成
metadata-only probe。它不是日文原文抽取，也沒有建立 source table、work ledger 或
翻譯。ROM、raw RAM／VRAM、字形 bytes、候選 stream 與 JSON receipt 均留在
`/private/tmp`；Git 只保留位址、計數、雜湊、控制流與工具規格。

## 固定輸入與重現

| 欄位 | 值 |
| --- | --- |
| ROM | `A9PJ`／`TOW SUMMLINE`／8 MiB |
| ROM SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| decoder version | `m20-text-record-probe-20260816.v1` |
| private metadata receipt | `/private/tmp/tow-a9pj-m20-text-metadata/summary-0x400.json` |
| command | `PYTHONDONTWRITEBYTECODE=1 python3 games/tales-of-the-world-summoners-lineage/tools/m20_text_record_probe.py /private/tmp/project-atlantis-a9pj.gba --candidate-limit 0 --output /private/tmp/tow-a9pj-m20-text-metadata/summary-0x400.json` |

工具只輸出 `source_text_emitted=false`、stream hash、record hash、位址與 aggregate
counts；不輸出 code-unit sequence、日文文字或 record rows。

## 已證實的 record geometry

靜態 Thumb 與 M1.6／M1.7 runtime receipt 共同支持下列鏈：

```text
16-bit code unit
  -> 0x080049A0 renderer
  -> 0x080049C8: code_unit * 0x18
  -> literal at 0x08004B00: 0x08089E00
  -> 24-byte record
  -> 0x08004A3A / 0x08004B16 ldrh record rows
```

對整個可計算的 unsigned 16-bit index 範圍做 metadata profile：

| 欄位 | 值 |
| --- | ---: |
| bus base／file base | `0x08089E00`／`0x89E00` |
| index range | `0x0000–0xFFFF` |
| record stride／length | `0x18`／24 bytes |
| record rows | 12 little-endian halfwords |
| table file range | `0x89E00–0x209E00` |
| records profiled | 65,536 |
| non-zero／blank records | 65,358／178 |
| distinct record SHA-256 | 63,427 |

這證明 table arithmetic 與 record 邊界可重跑，不證明每個 index 是日文 Unicode、
鍵盤字元或劇本文字。已觀察的兩個 runtime sample 仍為：

| code unit | record bus／file offset | record SHA-256 | identity |
| ---: | ---: | --- | --- |
| `0x005E` | `0x0808A6D0`／`0x8A6D0` | `aeac7e6ca436cfd8533f3171e8ddb3e790601dde94b1f7bedc5cfff3b9cad741` | keyboard table confirmed／transfer provisional |
| `0x0066` | `0x0808A790`／`0x8A790` | `207f45437ff6d4c5fae7598547f0b89c6670991689cd64f44ea26f87b320b964` | keyboard table confirmed／transfer provisional |

M1.7 的 runtime consumer 寫入 `0x060020xx/0x060023xx`，不是 BG1 keyboard
`0x06004020/0x06004040`；keyboard source→VRAM receipt 仍不存在，所以 confirmed
renderer transfer gate 仍未通過。M20 keyboard table probe 已另證 row 0 前五個
system-order mapping：`0x005E=あ`、`0x0062=い`、`0x0066=う`、`0x006B=え`、
`0x006F=お`；其中 `0x005E`／`0x0066` 有 M1.7 runtime consumer，故 keyboard glyph
identity 為 2 個 confirmed，renderer transfer 仍是 2 個 provisional。

## codepage 邊界

主要 null-terminated stream function 在 `0x080063E0`；固定長度 consumer 的
`0x080063B6 ldrh r3,[r5]` 以 16-bit little-endian code unit 消費資料，並在
`0x080063C2` 呼叫 `0x080049A0`。這是「index width confirmed」，不是「字元映射
confirmed」。M1.6 的 name-entry writer／reader 也以 16-bit `0x005E`、`0x0066`
重現這個寬度。

另一條 packed-layout caller 在 `0x080048DC` 以 `ldrb` 取 8-bit 值後於
`0x080048E4` 呼叫同一 renderer。它被工具明確記為 alternate 8-bit path，不與
16-bit text stream 合併成單一 codepage；目前尚未證明它是劇情文字。

## control-code 分欄

`0x080063E0` 的 parser behavior 有兩個靜態證據：

| 行為 | 位址／值 | 狀態 |
| --- | --- | --- |
| null terminator compare | `0x08006404`／`0x0000` | parser confirmed，實際 stream sequence 未做 runtime capture |
| special-token compare | `0x0800640E`／`0xFF70` | parser-behavior candidate |
| special-token path | `0x08006410` skip 2 bytes；`0x08006412` reset horizontal；`0x08006414` add `0x0C` vertical；`0x08006416` branch | 靜態 control-flow confirmed |

因此 `0xFF70` 目前只能叫作 line-advance candidate；工具不填入 semantic name，
也不把它當作 `{HH}` 翻譯控制碼。需要一次受控 runtime reader／parser capture，
取得實際 stream pointer、前後 code-unit hash 與畫面語境後，才可提升控制碼身份。

## 候選 pointer pool（未分類）

以 4-byte aligned ROM pointer 掃描 `0x1F0000–0x2C0000`，並以最多 `0x400` 個
16-bit units 做 bounded profile：

| 欄位 | 值 |
| --- | ---: |
| pointer references | 8,066 |
| distinct targets | 6,705 |
| NUL-terminated targets | 6,338 |
| capped／truncated targets | 367 |
| targets with `0xFF70` | 409 |
| `0xFF70` occurrences | 708 |
| role | `unclassified; pointer geometry alone is not text proof` |

這些 candidates 可能混有 UI、角色／戰鬥表、地圖／事件資料與 binary table。工具以
pointer offset／target／byte length 的 hash 產生 stable candidate ID，但不自動填寫
`locale`、`text`、語境或翻譯；因此尚未滿足 source-table row 的 runtime context
proof gate。

## 目前結論與最小缺口

| 維度 | 判定 |
| --- | --- |
| glyph addressing | `confirmed`: 16-bit index → `0x18` record arithmetic |
| glyph identity | `2 confirmed keyboard identities (0x005E=あ, 0x0066=う)；3 additional row-0 table mappings；general stream unknown` |
| codepage | `16-bit stream width confirmed; mapping unconfirmed`，8-bit packed path 分開 |
| terminator | `0x0000` parser branch confirmed，stream runtime sequence pending |
| control code | `0xFF70` line-advance behavior candidate，semantic identity pending |
| text pool roles | unclassified；不能自動標劇情／事件／選單／角色／戰鬥 |
| local source output | metadata receipt only；`research/*-decoded.jsonl` 尚未生成 |
| translation ledger | empty by design |

M1.7 的 private capture 另以 `m20_glyph_screen_cross_probe.py` 對齊四個 CPU-store
destination tile 與 BG0 screenblock `(14,4)/(14,5)/(15,4)/(15,5)`；但 immediate
post-store 與 final VRAM hash 有三筆不同，沒有把它誤升格成 byte-identical glyph
identity。完整 metadata negative 見
[`m20-glyph-screen-cross-20260816.md`](m20-glyph-screen-cross-20260816.md)。

下一個最小切片是單一 fresh mGBA／GDB connection，在既有 keyboard gate 或第一個可
重現選單／事件畫面只掛一個 `0x080063E0` entry breakpoint（必要時改掛
`0x080063B6` fixed-read site），讀取 `r2`／`r5` stream pointer、bounded halfword
window hash、位置參數與 LR；不把 raw stream 寫入 Git。已完成一次 reset→2 秒的
`0x080063E0` bounded negative，但未命中，只是否定該 startup window。只有 runtime
pointer、候選 record hash、terminator／`0xFF70` behavior 與畫面語境一致後，才建立
本機 ignored source rows。

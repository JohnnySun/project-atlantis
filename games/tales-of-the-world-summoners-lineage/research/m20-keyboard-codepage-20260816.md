# A9PJ M20 name-entry keyboard codepage slice（2026-08-16）

本切片用靜態控制流把 M1.6 的兩個 runtime code-unit observation 接回 name-entry
keyboard mapping table。它只保存五十音首列的少量已知 mapping、record hash、位址和
控制流；不輸出完整 record rows、ROM source stream、圖片或翻譯 ledger。

## table arithmetic 與 writer

`0x08052B94` 是 name-entry selection handler。已反組譯的關鍵 path 是：

```text
r4 = selection_index - 1
r1 = [keyboard_state]
r0 = (r1 << 6) + r1
r0 = r0 + r4
r0 = r0 << 1
r0 = r0 + 0x0808884C
ldrh r0, [r0]       ; 0x08052BB8
strh r0, [r3,#0xC]  ; 0x08052BBA -> observed EWRAM name slot
```

所以 table formula 是：

```text
0x0808884C + 2 * (row * 65 + selection_index)
```

這是 name-entry code-unit table 的實際 ROM read，不是從字形外觀猜測。M1.6 的
`0x02004014` writer `PC=0x08052BBC` 與此 `ldrh`／`strh` path 相鄰，M1.6/M1.7
又實際觀察到 `0x005E`、`0x0066` 被寫入並由 renderer 消費。

## row 0 首列 mapping

`m20_keyboard_codepage_probe.py` 以 A9PJ SHA-256
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` 重新讀取
`0x0808884C` row 0；前五個 entry 與系統五十音首列排列一致：

| row | selection index | system label | code unit | record bus | record SHA-256 | mapping status |
| ---: | ---: | --- | ---: | ---: | --- | --- |
| 0 | 0 | あ | `0x005E` | `0x0808A6D0` | `aeac7e6ca436cfd8533f3171e8ddb3e790601dde94b1f7bedc5cfff3b9cad741` | confirmed table mapping；runtime-backed |
| 0 | 1 | い | `0x0062` | `0x0808A730` | `8b5502e80f40be475e308f7c5446841fa2bde2d7a6c041a6e12b53d0ec94c41c` | confirmed table mapping；runtime tile pending |
| 0 | 2 | う | `0x0066` | `0x0808A790` | `207f45437ff6d4c5fae7598547f0b89c6670991689cd64f44ea26f87b320b964` | confirmed table mapping；runtime-backed |
| 0 | 3 | え | `0x006B` | `0x0808A808` | `7f9321e935f824a0111ed5b8e5c133c181abe69a534bf2dd6ad0c2a81abe231a` | confirmed table mapping；runtime tile pending |
| 0 | 4 | お | `0x006F` | `0x0808A868` | `8bf2728dc8731bd88be897b14311a2f814c1ace87ca62f0a6b4bd07a3f203210` | confirmed table mapping；runtime tile pending |

這個結果修正先前 M1.6/M1.7 中把第二次 `A` 的 `0x0066` 暫註成 `a-row-2／い` 的
說法：就已證實的 ROM keyboard table 而言，`0x0066` 是 row 0 的 selection index 2，
即 `う`。舊註解是 input path 的 provisional layout annotation，不是 codepage proof。

## 身分與 transfer gate 分離

對 `0x005E`／`0x0066`，目前可以分開寫成：

| 維度 | 判定 |
| --- | --- |
| code unit → keyboard identity | confirmed：實際 table arithmetic + 系統 row-order |
| code unit → font record | confirmed：`0x08089E00 + unit*0x18`、record hash、M1.7 read receipt |
| record → CPU renderer | confirmed：`0x08004C82`／`0x08004D1A`、writer `cpu-game-rom` |
| renderer store → final screen bytes | not confirmed：M20 BG0 cross receipt 有三筆 final hash mismatch |
| DMA／BIOS source copy | not observed；不以 CPU store 代稱 DMA |
| general text stream codepage | unconfirmed；row 0 keyboard table 不等於所有劇情／事件資料 |

因此本切片提升的是 **兩個 code-unit 的鍵盤 identity**，不是完成 BG1 asset provenance
或一般 script decoder。2A source-table gate 仍關閉；最小下一步是取得 row 0 其餘項的
runtime store／screen receipt，並對 `0x080063B6`／`0x080063E0` 取得實際 text-stream
context。

## 重跑與輸出界線

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m20_keyboard_codepage_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --row 0 --count 5 \
  --output /private/tmp/tow-a9pj-m20-keyboard-codepage/summary-row0-first5.json
```

工具輸出 `source_text_emitted=false`、table／record 位址、hash、bitmap counts 和
mapping status；不輸出 record rows、完整原文或 source table。

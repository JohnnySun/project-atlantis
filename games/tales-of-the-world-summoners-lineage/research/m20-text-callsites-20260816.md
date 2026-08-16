# A9PJ M20 text-consumer callsite index（2026-08-16）

本切片對 clean A9PJ ROM 做 aligned Thumb-1 BL callsite index，只追蹤已由 M20 static
control-flow 證實的三個 consumer entry。它是 caller／pointer metadata，不是 runtime
scene classification，也不輸出 stream bytes、code-unit sequence 或原文。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m20_text_callsite_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --max-units 0x80 --limit 256 \
  --output /private/tmp/tow-a9pj-m20-callsite/summary.json
```

ROM SHA-256 是 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
tool version 是 `m20-text-callsite-probe-20260816.v1`；輸出含 private stream hash、
終止／控制候選計數、literal pointer file offset、簡單寄存器 provenance 與
`source_text_emitted=false`。

## static counts

| consumer | callsites | profiled | ROM literal pointer streams | NUL terminated | streams with `0xFF70` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0x080063E0` null parser | 126 | 126 | 46 | 46 | 4 |
| `0x0800638C` fixed-count reader | 10 | 10 | 0 | 0 | 0 |
| `0x0800644C` alternate fixed/control consumer | 83 | 83 | 0 | 0 | 0 |

`0x080063E0` 的 126 個 callsite profile role 分布是：53 個沒有簡單 `r2` literal、27
個是 non-ROM／runtime-like pointer、46 個是 ROM pointer stream candidate。這些數字
只說明 caller 的靜態形狀；合法 NUL 結尾或 `0xFF70` 不足以證明是劇情、地圖／事件、
角色、戰鬥或 UI。

## 可重現 caller evidence

代表性 ROM-literal caller（只列位址與 metadata，不列 stream）如下：

| callsite | pointer target | caller arguments | bounded profile |
| ---: | ---: | --- | --- |
| `0x08015E92` | `0x1FA616` | `r1=0x21`、`r3=0x0F` | 20 units、NUL、1 control candidate |
| `0x08015EA6` | `0x1FA666` | `r1=0x21`、`r3=0x0F` | 20 units、NUL、1 control candidate |
| `0x080196F2` | `0x1FA5B0` | `r1=0x21`、`r3=0x0F` | 4 units、NUL、no control candidate |
| `0x08024A78` | `0x1FA3A2` | `r1=0x00`、`r3=0x0F` | 9 units、NUL、no control candidate |
| `0x080509CC` | `0x1FAA24` | `r0=0x00000002`、`r1=0x21`、`r3=0x0F` | 18 units、NUL、no control candidate |
| `0x08066B76` | `0x20070A` | `r1=0x21`、`r3=0x0F` | 38 units、NUL、3 control candidates |

Callsite `0x08015E92`／`0x08015EA6` 同時符合「ROM pointer + parser caller」的幾何條件，
但沒有 runtime screen／caller state，因此仍是 `unclassified`。這些 pointer target
可作為下一次單一 breakpoint 的候選，不可直接產生 source table row。

## 判定與下一個最小缺口

| 維度 | 判定 |
| --- | --- |
| BL target／caller index | confirmed static |
| ROM pointer／bounded stream geometry | confirmed static candidate |
| parser／record boundary | static 16-bit／`0x0000`／`0xFF70` behavior 已有 |
| scene role | unknown；runtime context 未取得 |
| source table／ledger | closed；沒有建立 source row 或翻譯 |

下一個最小 runtime slice 是從一個 caller（優先 `0x08015E92`）或其 parser entry 設置
單一 breakpoint，在可重現選單／事件畫面取得 pointer、LR、畫面 hash 與 bounded stream
hash。socket protocol 未成功時，維持本 static index，不把 caller profile 當成 runtime
命中。

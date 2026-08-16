# A9PJ M20 runtime text-reader probe boundary（2026-08-16）

本紀錄只保存 bounded protocol 結果，不保存 stream bytes、code-unit sequence 或畫面
圖片。工具 `m20_text_runtime_probe.py` 使用共用 `core/gba/gdbstub_client.py`，每次
只掛一個 text breakpoint cohort：

| mode | breakpoint | pointer register | purpose |
| --- | ---: | --- | --- |
| `null-entry` | `0x080063E0` | `r2` | null-terminated parser entry |
| `fixed-read` | `0x080063B6` | `r5` | fixed consumer `ldrh` read site |

可選的 `--navigate-sequence` 只覆寫已授權的 KEYINPUT input register；工具不寫 game RAM，
text window 只輸出 hash、counts、region、PC/LR 與 candidate ID。

## 已完成的 bounded attempts

### reset-only null-entry negative

| 欄位 | 值 |
| --- | --- |
| private receipt | `/private/tmp/tow-a9pj-m20-text-runtime-2/summary.json` |
| mGBA | fresh A9PJ，session-owned `39123` listener |
| breakpoint | `0x080063E0`，cohort `1`，pointer `r2` |
| initial stop | `S02`，`pc=0` |
| navigation | disabled；register／memory writes `0/0` |
| result | 2 秒 bounded timeout，`hit_count=0`，interrupt stop `S02` |

這只是否定 **reset 到 2 秒的該 parser entry window**；不能解讀成遊戲沒有文字
consumer，也沒有用 timeout 代替事件／選單證據。

### fresh fixed-read connection failure

另啟動本 session 自己的 fresh mGBA A9PJ process；GDB listener 可由 lsof 確認，但
`fixed-read` 加 `START,START,A` 的 client 在初始 protocol 建立階段只回報
`status=connection-failed,error=OSError`，沒有 `protocol`、navigation、register 或
breakpoint hit receipt。這不是文字路徑的陰性證據，不能列為 hit `0`；自己的 mGBA
process 已停止，沒有留下 listener。

## 判定與下一步

| 維度 | 判定 |
| --- | --- |
| text reader address | static `0x080063E0`／`0x080063B6`，runtime hit 未取得 |
| codepage width | static／M1.6 16-bit evidence 已有；runtime stream sequence 未取得 |
| terminator／`0xFF70` | static parser behavior candidate；runtime semantic 未取得 |
| scene role | unknown；不能分類為劇情、事件、角色、戰鬥或 UI |
| source table／ledger | closed；沒有建立 local decoded rows 或翻譯 |

下一個最小可重跑切片仍是單一乾淨 GDB connection，在已通過的 keyboard gate 或可重現
選單／事件畫面命中 `0x080063B6`／`0x080063E0`，並取得 stream pointer 的 bounded
hash 與畫面 metadata。若 socket 服務再度不可用，先保留本紀錄與 static candidates，
不得把 connection failure 改寫成 runtime negative。

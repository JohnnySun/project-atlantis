# A9PJ M1 有界 GDB 擷取紀錄（2026-08-16）

本紀錄只保存執行期協定結果與判定界線，不保存 ROM、畫面、VRAM dump、字型資料或
日文原文。這是一次且僅一次的 bounded capture；沒有把失敗的停點當成文字路徑。

## 擷取 receipt

| 欄位 | 值 |
| --- | --- |
| ROM | A9PJ clean dump，SHA-256 `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| mGBA | 本 session 的暫存 build；binary 與任何修改都在 `/private/tmp` |
| GDB listener | `127.0.0.1:23901`，只供本 session 使用 |
| 候選 watchpoint | GBA ROM `0x081ff000`，對應 file offset `0x1ff000` 的候選區 |
| GDB packet | `Z3,81ff000,1000`（read watchpoint，4 KiB range） |
| continue budget | 12 秒；連線 timeout 後停止本 session 自己的 mGBA |

## 實際觀察

1. 新鮮 mGBA session 可連線；`?` 回覆 `S02`，表示 target 在初始停住狀態。
2. `Z3,81ff000,1000` 回覆 `OK`。這只代表 mGBA stub 接受了設定，不能單獨證明
   硬體能以這個範圍攔截所有 ROM read。
3. 發送 `c` 後，在 12 秒 budget 內沒有收到完整的 GDB stop packet；client 回報
   `TimeoutError: no complete packet received`。
4. 因為沒有 stop packet，本次沒有可合法記錄的 stop PC、來源暫存器、實際讀取位址、
   IWRAM／VRAM 狀態或 glyph 搬移。連線關閉後，已核對並停止唯一載入 A9PJ 的
   `23901` mGBA 程序；其他 listener 未觸碰。

## 判定

| 證據項目 | 判定 | 原因 |
| --- | --- | --- |
| 候選區被遊戲實際消費 | `not-confirmed` | 沒有 watchpoint stop；`OK` 不是 memory-access evidence |
| 事件／選單文字 consumer | `not-confirmed` | 沒有命中 PC 或呼叫上下文 |
| 控制碼 | `not-confirmed` | 沒有讀值序列或 parser stop |
| glyph／VRAM 搬移 | `not-confirmed` | 沒有可歸屬於文字的 DMA／VRAM evidence |
| codepage／16-bit 字元身份 | `not-confirmed` | M0 的 little-endian 候選仍只有靜態幾何證據 |
| source table | `blocked` | 尚未達到來源位址、邊界、碼頁與語境的交叉證據門檻 |
| zh-TW work ledger | `empty-by-design` | 沒有建立會依賴猜測 string ID 或 source hash 的假資料 |

## 可重現的協定摘要

在合法的本機 A9PJ dump 與獨立 mGBA/GDB session 上，重跑時至少要保存以下 metadata：

```text
connect 127.0.0.1:23901
?                         -> S02
Z3,81ff000,1000           -> OK
c                         -> no stop packet within 12 seconds
```

這個摘要可重現「stub 接受設定但未取得命中」的負結果；不能當成文字 decoder，也不能
用來生成 `source.text`。下一次任何 runtime 研究都必須取得新的明確授權與新的 bounded
scope，不在本 receipt 之外延伸 mGBA 偵察。

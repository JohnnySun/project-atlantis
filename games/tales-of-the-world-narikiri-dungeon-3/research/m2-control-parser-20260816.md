# M2 固定控制 parser 靜態邊界（2026-08-16）

## 目的與範圍

本回合只驗證從 B3TJ executable code 已鎖定的狹窄 THUMB span，不做新的
pointer scan、不修改 ROM、不讀寫 mGBA state，也不把畫面 OCR 當作 source table。
可重跑工具是
[`tools/control_parser_probe.py`](../tools/control_parser_probe.py)，輸出只含
ROM identity、位址、signature/hash 與計數；完整指令 bytes 不進 Git。

## Confirmed：固定的 static control-parser contract

`0x080025CC`（file offset `0x25CC`）的 bounded code 具有下列可重現結構：

- entry 將第一參數保存到 IWRAM `0x03001588`，以第二參數作為逐 byte input；
- ordinary byte 從 `0x080027E4` copy 到同一 cursor，`0x080027F2` 重複讀取並在
  NUL 結束；
- `0x25`（ASCII `%`）在 `0x080025E0` 進入控制流程；命令 byte 於
  `0x08002618` 減去 `0x25`，`0x0800261A` 以 `0x53` 作上限；
- dispatch literal 位於 file `0x262C`，值為 `0x08002630`。該表恰有 `0x54`
  個 word，覆蓋 `%` 到 `x` 的 command range；72 個 entry 回到 loop，12 個
  entry 進入明確 case handler。所有 target 都落在已審核的
  `0x08002780–0x080027F2` bounded case span；
- `0x080027FA` 寫入 output NUL。`0x08002814` 是一個狹窄 wrapper，
  `0x08002828` 是以 `0x1F` 門檻計數的 adjacent helper；`0x08002844` 與
  `0x080028B0` 會以同一個 ROM literal `0x080FFD86` 查 signed halfword，
  因而只能標為 width-helper candidate。

`research/m2-control-parser-metadata.json` 是本回合對同一 ROM 的 probe receipt。

## Provisional：仍未連到哪一筆文字

這段 code 的 input/output register 形狀、NUL 結束與 `%` command dispatch 已經是
confirmed static；它很像文字／格式 buffer parser，但目前沒有 live breakpoint
命中本段，也沒有把五個 strict Shift-JIS window 的 concrete `string_id` 連到
entry。既有 M1.8 clean `--trace-first-record` 仍是 resolver hit 4、strict source
read 0，因此這裡不能宣稱「已確認 live text consumer」。

Ledger 已記錄的 `%0t`、`%0g`、`%h`、`%k`、`%l`、`%d` 等 token 只證明靜態候選的
語法交集；它們的參數語義、控制碼作用與可替換容量尚未由 runtime 驗證。

## Negative／unknown 邊界

- `runtime_text_consumer`: **unconfirmed**；尚無 source read PC/LR、destination
  buffer 或 caller receipt。
- `japanese_codepage`／`glyph_identity`: **unconfirmed**；`0x08002844`／
  `0x080028B0` 只能視為 width lookup candidate，不是 glyph table 證明。
- ROM→RAM→glyph/VRAM 因果鏈：**未取得**；不能用 UI 畫面 hash 代替。
- capacity、pointer update、compression boundary、round-trip 與 insertion：
  **unconfirmed**，因此仍禁止翻譯與 BPS 回插。

下一個最小切片是：在可用的獨立 mGBA session 對 `0x080025CC`／`0x08002814`
設單一入口 breakpoint，沿既有正常流程取得一次 input pointer、cursor global、
return length 與 caller；若無法重現，至少維持這份嚴格 static receipt，不擴大掃描。

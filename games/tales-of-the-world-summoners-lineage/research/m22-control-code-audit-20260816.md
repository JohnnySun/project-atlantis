# A9PJ M22 control-code candidate audit（2026-08-16）

本切片只做 static bounded audit，不把 pointer geometry 或頻率當成 runtime scene
證據，也沒有建立 source table、work ledger 或翻譯。工具只寫 caller 指定的 private／
ignored JSON receipt；Git 保留版本、位址、計數、分類與 hash，不保留 stream bytes、
日文原文、glyph rows 或圖片。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m22_control_code_probe.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m22-control/summary.json
```

工具版本為 `m22-control-code-probe-20260816.v1`，輸入預期為 A9PJ SHA-256
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。它重用 M20 的
4-byte aligned pointer candidates 與最多 `0x400` 個 little-endian halfword 的 bounded
stream boundary，並以 target 去重後計算 aggregate。輸出沒有 `units` 或 `text` 欄位。

本輪 receipt 為 8,066 個 references、6,705 個去重 targets，其中 6,338 個以 `0x0000`
終止、367 個到達 bounded cap；827,181 個 halfwords 中，`0x0000` 有 6,338 次、
`0xFF70` 有 708 次、`0x0001` 有 10,435 次。`0x0001` 對應的全零 record candidate
出現在 1,584 個 target；其餘頻率最高的 units 仍呈現二進位／資料表形狀，不能用來
擴張 text codepage。aggregate frequency SHA-256 為
`214e3d62985667f41d6ce2be85beb4503e584c16a4f2d07bc2b9f31515adfff5`。

## 審計結論

- `0x0000` 仍是 parser 的終止分支；本輪只取得 candidate stream count，沒有 runtime
  reader stop，因此不把所有 NUL rows 當劇情。
- `0xFF70` 仍是 parser special branch／換行候選；`skip 2`、horizontal reset 與
  vertical `+0x0C` 是 static behavior，semantic control name 仍未確認。
- `0x0001` 對應 all-zero 24-byte font record，另列為 blank-record candidate；它可能是
  空白、鍵盤空格、padding 或其他 sentinel，不能直接寫成 U+0020，也不能當控制碼。
- 其他 halfword 維持 `font-record-index`，不因低數值、出現頻率或合法 table address
  自動改成控制碼。候選池的 scene role 仍是 `unclassified`、`eligible_for_ledger=false`。

## runtime 邊界

本輪曾以本 session 自有 A9PJ headless mGBA 啟動單一 39123 嘗試；進程可運作但輸出
`Debugger: Couldn't open socket`，沒有 listener，固定 reader／parser 也沒有取得
register、PC/LR、stream pointer 或 screen receipt。進程已停止；23901 是其他遊戲的
session，沒有連線或停止。這是本機 debugger availability negative，不是文字 consumer
不存在的證據，故不改寫 M20 的 runtime `connection-failed`／startup-window negative。

## 下一個最小缺口

需要一個可建立 listener 的 fresh A9PJ runtime，在單一 `0x080063E0` 或 `0x080063B6`
cohort 命中後，同時保存 stream pointer hash、`0x0000`／`0xFF70` 前後 bounded
metadata、caller LR 與畫面 hash；只有這些和 scene gate 同時成立，才可開啟 row role、
control semantic 或 ledger eligibility。

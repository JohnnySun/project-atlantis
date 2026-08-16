# A9PJ M24 direct null-renderer candidate decoder（2026-08-16）

M24 將 M21 的 broad pointer pool 收窄到 clean ROM 中直接以 ROM literal pointer 呼叫
`0x080063E0` 的 16-bit NUL stream。這是 static caller evidence，不是 runtime hit；所有
local rows 固定 `runtime_context=false`、`scene_role=unclassified`、
`eligible_for_ledger=false`。JSONL 只寫 `/private/tmp` 或 ignored `research/*-decoded.jsonl`，
不進 Git。

## 重現

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m24_direct_callsite_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --output /private/tmp/tow-a9pj-m24-direct/direct-decoded.jsonl
```

版本為 `m24-direct-callsite-decoder-20260816.v1`，重用 M20 Thumb BL／literal provenance、
M20 record boundary 與 M21 partial keyboard mapping。每個 row 的 stable ID 同時含
caller file offset、target file offset、bounded byte length；同一個 stream 被不同 caller
引用時不會靜默合併。stdout 只回報 counts／hash，local JSONL 才有 `text`。

## private aggregate receipt

本輪 clean A9PJ 產生 46 個 direct static caller rows、28 個 distinct stream targets；它們
全部以 `0x0000` 結尾，但仍含未解 halfword，沒有 row 通過 complete codepage。直接 caller
池比 8,066 個 broad references 更適合後續全字串 raster／context alignment，但暫時不能
命名為劇情、地圖／事件、角色、戰鬥或 UI。

第一個 bounded render candidate 是 caller `0x08015E92` → stream file offset `0x1FA616`；
M23 static raster 可在 private image 中以已知假名 landmark 檢查 bit order。未知 glyph 的
圖形閱讀、OCR 或英文 patch 對照都只作 local candidate，不能直接寫進翻譯 ledger。

## 下一個最小缺口

在 direct caller 或其上一層取得一次 fresh runtime breakpoint，保存 caller state、stream
pointer、畫面 hash 與 bounded source hash；若該 caller 確認為穩定 UI／事件語境，再對
同一池做全字串 codepage alignment，逐項標記 confirmed／context-provisional／unknown。

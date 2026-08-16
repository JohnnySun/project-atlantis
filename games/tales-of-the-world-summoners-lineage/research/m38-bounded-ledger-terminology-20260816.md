# A9PJ M38 bounded ledger／術語 receipt（2026-08-16）

M38 只處理 M34 已通過 known-screen proof 的第二條姓名 row。它不新增 pointer
candidate、不擴張 provisional decoder，也不把官方 Latin 選擇誤報成完整 zh-TW 術語
表。ROM、source table、工作記錄、raw bytes 與 patched image 均留在本機 ignored／
`/private/tmp`。

## 固定輸入與 ledger gate

沿用 M35 的固定 `--known-ui-only` decoder 與 M34 row：A9PJ ROM SHA-256 為
`b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`，stable ID 為
`f4bc65e10318a0204bebc5b0`，source span file offset 為 `0x087384`，terminated
source hash 為 `8c24214195799be96f68bbd812d4ae8de1a086856c20846cf18c629f1f4283e4`。
M34 的四個 record、四個 raster mask 與八個 BG0 tilemap／tile receipt 仍是本 row
唯一的 glyph identity proof；`runtime_context=false`、`general_codepage=false`、
`control_schema=false` 不變。

M38 把私有 working record 經 `core/ledger/strip_translations.rb` 產出的安全記錄
寫入 `translations/m34-ui-row.jsonl`。提交檔只含 `source_hash`，沒有 `source` 物件、
source text、record bytes 或完整原文。既有 `translations/m32-ui-row.jsonl` 與它
共同形成目前兩條、且僅限 known-screen 的最小 ledger POC。

## 術語決策

目前兩個 eligible row 只涵蓋主角姓名欄位的 given-name／surname 片段。官方 Bandai
Namco 角色頁使用 `Fulein.K.Lester`，官方／日文獨立資料維持同一拉丁姓氏；本次補充
的[巴哈姆特 GNN 報導](https://gnn.gamer.com.tw/detail.php?sn=8364)在臺灣語境也直接
使用 `Fulein Lester`。因此目前 bounded `zh-TW` target 保留 `Fulein`／`Lester`
官方 Latin，不自行創造漢字音譯；這是「臺灣來源採用 Latin」的可審核決策，不是宣稱
已存在漢字主流譯名。

Wikipedia zh-tw 與巴哈姆特社群頁面仍沒有可直接核對本作角色的漢字條目；故人名狀態
仍是 bounded／AI draft，待日後若出現更強的臺灣社群慣用名再人工複核。地名、其他
角色、職業、技能、道具、戰鬥與地圖術語沒有被這條 row 證明，維持 pending。

## 可重跑檢查與結果

私有 source table 與 work output 的重建命令（輸入／輸出均不進 Git）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m21_source_decoder.py \
  /private/tmp/project-atlantis-a9pj.gba --known-ui-only \
  --output /private/tmp/tow-a9pj-m35-known-ui/summoners-lineage-known-ui-decoded.jsonl

ruby core/ledger/restore_translations.rb \
  games/tales-of-the-world-summoners-lineage/translations/m34-ui-row.jsonl \
  /private/tmp/tow-a9pj-m34-ledger/source.jsonl \
  /private/tmp/tow-a9pj-m38-ledger/restored.jsonl

ruby core/ledger/strip_translations.rb \
  /private/tmp/tow-a9pj-m38-ledger/restored.jsonl \
  /private/tmp/tow-a9pj-m38-ledger/stripped.jsonl
```

本次 receipt：

| check | result |
| --- | --- |
| known-screen rows | M32/M34 `2/2`，terminated／complete `2/2` |
| M34 source hash | match；`8c2421…f4283e4` |
| restore／strip | one row，stable ID preserved，source hash preserved |
| stripped output | no `source` key；與提交列 schema 相同 |
| zh-TW target | official Latin `Fulein`，width budget `54`，one line |
| general codepage／non-UI scene | false／`0` |
| patched mGBA runtime QA | not run／not claimed |

本機驗證結果：game-specific unittest `83` tests passed，shared `core/gba` unittest
`31` tests passed，core ledger codec `4` tests／`7` assertions passed，translation
ledger schema smoke passed（2 files），`scripts/check-repository-safety.rb` passed
（1097 visible files），且 `git diff --check` 無輸出。

M33／M34 的 bounded relocation 與 BPS apply receipt 仍只證明 Latin target plumbing；
M38 沒有把它升格成 CJK encoder、fixed-slot policy 或可玩的完整 patch。

## 下一個最小缺口

先補一條可獨立驗證的非 UI scene／general Japanese-CJK mapping 或 live control consumer，
再擴 source table 與翻譯批次。若 runtime socket 仍不可用，必須以固定 source pointer、
record raster、畫面／tilemap 與可重抽取的已知句列建立下一個 bounded row；不得重新開
M29+ provisional candidate layer。

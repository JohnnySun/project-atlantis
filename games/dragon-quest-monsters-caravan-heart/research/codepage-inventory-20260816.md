# Clean A9HJ codepage inventory

日期：2026-08-16

這份 receipt 只統計 clean extractor 的 token 類別與 code-unit 使用次數，
不保存或輸出任何原始腳本文字。輸入是被 `.gitignore` 排除的
`research/dragon-quest-monsters-caravan-heart-decoded.jsonl`；正式基準固定為：

- ROM size：8,388,608 bytes
- CRC32：`3C24ABCC`
- SHA-256：`FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`
- extractor schema：`dqmch-clean-script-bytes-v1`

可重現命令：

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_codepage_inventory.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-codepage-inventory.json
```

## Clean receipt

執行結果摘要：

- 37,600 records、4,879 個 unique pointers、6 groups、36 variants。
- 36,509 records 含 `FF` candidate；這只是統計，不把 `FF` 宣稱為通用終止碼。
- 103,209 個 pair tokens；其中 98,108 個依目前已核對的假名濁音／半濁音表可解，
  5,101 個仍未解。
- 39,225 個 alternate-glyph tokens：`E0` 為 31,383、`E1` 為 7,842；共使用
  471 個 `(lead,index)` slots。這確認使用範圍，但不替未命名 alternate glyph
  猜測 Unicode identity。
- 217,774 個 control candidates；它們仍須配合 state-dependent handler context，
  不可由出現頻率直接推導語義。
- direct single-byte path 使用 188 個已定義 atlas units，另有 33 個未定義的
  direct units；未定義 units 仍以 `{Uxx}` 保留在本機 source table。
- v2 receipt 另外產生 83 個有未定義 direct unit 的 `group`／`variant` context buckets：
  `g00` 的每 variant 為 136、`g01` 為 470／472、`g02` 為 113、`g03` 為 945、`g04`
  為 24、`g05` 為 23、`g06` 為 82、`g07` 為 1,579。這些固定／重複的計數形狀把
  `0xB8`／`0xBE`／`0xC0..0xDE` 限定為需要 context 的 pointer-pool residue；它是
  結構性訊號，不是把該區間升格成 glyph identity 的依據。

## Direct codepage corroboration

公開的 Caravan Heart code table 明列 `0x00..0xBD` 的數字、假名、濁音／半濁音、
標點與 UI glyph；本工作區只把它當作 codepage engineering corroboration，沒有
採用任何英文／中文翻譯。clean ROM 的 `0x2DF3D4` glyph atlas 與實際 token 使用
範圍共同核對了 direct map；`0xB8`、`0xBE` 與 `0xC0..0xDE` 仍未命名，故不因
表格相鄰性填值。參照：[公開字碼表](https://gbacode.ame-zaiku.com/gba-dragon_quest_monsters.html)、
[另一份日文 code table](https://www.arcenserv.info/gba/cheat/%E3%83%89%E3%83%A9%E3%82%B4%E3%83%B3%E3%82%AF%E3%82%A8%E3%82%B9%E3%83%88-%E3%83%A2%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E3%82%BA-%E3%82%AD%E3%83%A3%E3%83%A9%E3%83%90%E3%83%B3%E3%83%8F%E3%83%BC%E3%83%88/)。

## 解讀與邊界

inventory 將單 byte、`0x92`／`0x93` pair、`E0`／`E1` alternate-glyph 與
`DF..FF` control candidate 分開計數。`E0`／`E1` 是已證明的 glyph-pool look-ahead，
不是 control dispatch 的同義物；控制碼的 source-parameter 形狀另見
`research/control-consumption-20260816.md`。

因此本 receipt 完成的是「使用範圍與未解集合的可重現盤點」，不是完整 codepage、
alt-pool glyph identity、控制碼語義、script boundary 或 encoder。它不會使 M1
的完整格式 gate 或 M2 全量 ledger gate 自動通過。

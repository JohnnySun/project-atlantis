# Clean text source/output cursor contract（2026-08-17）

以正式 clean A9HJ ROM（CRC32 `3C24ABCC`、SHA-256
`FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`）執行共用
`scripts/gba-rom-identity.py`，再執行本作的 bounded `tools/audit_text_cursor.py`。
ROM identity 的 expected values 維持在本作 `game.yml`／README；本 receipt 與工具只檢查
Thumb code signatures，不輸出 script bytes、完整原文、glyph identity 或翻譯來源。

## 已固定的資料流

- `0x08012628`：在 parser 的 default path 讀 `state+0x18`，將該 source pointer 前進一
  byte，再從原游標讀取資料。
- `0x08012630`：把目前 byte 的低位結果放入 `state+0x20`，呼叫
  `0x0801266C` handler。
- `0x08012720`：在 pair path 再從 `state+0x18` 前進一 byte 並讀第二 byte。
- `0x08012728`：將第一／第二 byte 傳入 `0x08013738` pair combiner。
- `0x080137DE`／`0x08013E1A`：pair／single writer 都用獨立的
  `state+0x16` output slot 與 32／64-byte glyph stride 計算 DMA3 destination。
- `0x080137FE`／`0x08013E34`：兩個 writer 各自對 `state+0x16` 做一次 `+1`。
- `0x080125FA` 另記錄 alternate state path 對 `state+0x1C` 的遞增；這條路徑尚未被
  升格成可直接抽取的 record boundary 規則。

## 判定與限制

這證明 source cursor `state+0x18` 與 output slot `state+0x16` 是不同狀態欄位，並固定了
兩條有限 parser path 的 byte advance 與 pair dispatch。它不證明 `FF` 是終止符，也不證明
`state+0x16` 的 slot advance 是 Unicode 字寬或完整 VWF cursor；width table、換行／換頁、
溢位、alternate handler semantics 與所有 script record boundaries 仍開放。

## 重現

```text
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/gba-rom-identity.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  --expect-size 8388608 --expect-game-code A9HJ --expect-crc32 3C24ABCC \
  --expect-sha256 FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE \
  --output /private/tmp/dqmch-a9hj-identity-20260817.json
# exit=0, status=pass

同一 expected contract 對歷史 32 MiB candidate 執行 identity CLI 得到 exit `1`、
`status=fail`；candidate 僅保留為被排除的本機對照，不進入 static audit、抽取、翻譯或回插。

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/dragon-quest-monsters-caravan-heart/tools/audit_text_cursor.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  --expect-size 8388608 --expect-game-code A9HJ --expect-crc32 3C24ABCC \
  --expect-sha256 FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE
schema dqmch-text-cursor-contract-v1
identity-gate pass
signatures 7 advance-signatures 2
semantic_width_or_vwf not-proven
record_boundary not-proven
```

測試另外以一個 byte mutation 確認 signature gate 會拒絕變更後的 ROM；完整遊戲抽取、
semantic encoder、VWF／版面與 runtime QA 不因這項 static receipt 而宣稱完成。

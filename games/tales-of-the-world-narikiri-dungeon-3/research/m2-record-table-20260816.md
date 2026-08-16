# M2 固定 direct-record table provenance（2026-08-16）

## 範圍

這是一個已在 M1.5 找到的固定 table 之再驗證，不是新的廣泛 pointer scan。
`tools/direct_record_table_probe.py` 只讀 file `0x0DD1B84–0x0DD1BB4` 的 12
個 absolute GBA words，交叉既有 strict extractor 的 record boundary，輸出
stable ID、offset、raw length、hash 與計數；不輸出原文或 raw table bytes。

## Confirmed static

ROM `B3TJ` 的 12-entry table 全部是 direct absolute pointer，目標順序為 file
offset descending：

`0x146F10, 0x146F08, 0x146F00, 0x146EF8, 0x146EF0, 0x146EE8,
0x146EE0, 0x146ED8, 0x146ED0, 0x146EC8, 0x146EBC, 0x146EB4`。

12/12 個 target 都是五窗 strict record，且全在 `text-pool`；raw length 為 4–8
bytes，target delta 有 10 個 `0x08` 與 1 個 `0x0C`。selected
`sjis:0x146EE0` 位於該 table 的第 7 個 target，table word file offset 是
`0x0DD19C`。receipt 的 table SHA-256 是
`43f4e47173af72cf8b14aff2f5dba479e015e8035f9f780a1da624b2de93179a`，target
order SHA-256 是
`5e51f8cd78a6fe405d4639d756fbdbe4ebeef0c8741af87d0a4e599ac81a6042`。

## Capacity／category boundary

這個 table 證明的是 pointer provenance，不是 record slot capacity：target spacing
與 raw length 不同，僅由 pointer bytes 不能決定可用餘裕、padding、length field、
排序意義或回寫後是否需要更新其他 index。它也尚未分類為事件、角色／服裝、技能、
戰鬥或選單；`text-pool-subtable` 仍是唯一安全分類。

既有 M1.8 clean `--trace-first-record` 對 selected `0x146EE0` 仍為 source read
0，因此這份 direct table receipt 不會升格成 live consumer。pointer rewrite、
容量檢查、compression boundary、round-trip 與翻譯仍是 **unconfirmed**。

下一個最小 runtime 切片仍是從已確認的 `0x080025CC`／`0x080014F4`／
`0x08001E26` static chain 取得 source pointer→formatted buffer→IWRAM writer；
成功前不開始寫譯文或 BPS。
